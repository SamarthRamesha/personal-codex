#!/usr/bin/env python3
"""Resolve public official Python OCI metadata only. No layers, image pull, build or install."""
import argparse
import hashlib
import http.client
import json
from pathlib import Path
import ssl
import time
from urllib.parse import urlsplit

MAX_METADATA=262144
TAG='3.13-slim-bookworm'


def get(host,path,headers=None,redirected=False):
    connection=http.client.HTTPSConnection(host,timeout=10,context=ssl.create_default_context())
    try:
        connection.request('GET',path,headers=headers or {});response=connection.getresponse()
        if response.status in {302,307} and host=='registry-1.docker.io' and not redirected:
            location=urlsplit(response.getheader('Location',''))
            if location.scheme!='https' or location.hostname!='production.cloudfront.docker.com' or location.port not in (None,443) or location.username or location.fragment:
                raise ValueError('Unapproved metadata redirect')
            # Public content-addressed config only; never forward the registry Authorization header.
            return get(location.hostname,location.path+('?' + location.query if location.query else ''),redirected=True)
        raw=response.read(MAX_METADATA+1)
        if response.status!=200 or len(raw)>MAX_METADATA:raise ValueError('Official registry metadata unavailable or exceeds limit')
        return raw,dict(response.getheaders())
    finally:connection.close()


def document(raw,digest=None):
    actual='sha256:'+hashlib.sha256(raw).hexdigest()
    if digest and digest!=actual:raise ValueError('OCI metadata digest mismatch')
    return json.loads(raw),actual


def resolve():
    raw,_=get('auth.docker.io','/token?service=registry.docker.io&scope=repository:library/python:pull')
    token=json.loads(raw)['token']
    headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.docker.distribution.manifest.v2+json'}
    raw,_=get('registry-1.docker.io','/v2/library/python/manifests/'+TAG,headers)
    index,index_digest=document(raw)
    selected=[item for item in index['manifests'] if item.get('platform',{}).get('os')=='linux' and item.get('platform',{}).get('architecture')=='amd64']
    if len(selected)!=1:raise ValueError('One unambiguous Linux amd64 image required')
    child=selected[0]['digest'];raw,_=get('registry-1.docker.io','/v2/library/python/manifests/'+child,headers)
    manifest,_=document(raw,child)
    if manifest['config']['size']>MAX_METADATA:raise ValueError('Image config exceeds metadata budget')
    raw,_=get('registry-1.docker.io','/v2/library/python/blobs/'+manifest['config']['digest'],headers)
    config,_=document(raw,manifest['config']['digest'])
    if config.get('os')!='linux' or config.get('architecture')!='amd64' or config.get('config',{}).get('Volumes') or config.get('config',{}).get('OnBuild'):
        raise ValueError('Unexpected base architecture, implicit volumes or build triggers')
    return {'version':1,'source':'Docker Official Images / library/python','tag':TAG,'checked_at_unix':int(time.time()),'index_digest':index_digest,
            'platform':'linux/amd64','base_image':'docker.io/library/python@'+child,'config_digest':manifest['config']['digest'],
            'compressed_layer_bytes':sum(layer['size'] for layer in manifest['layers']),'layers':[{'digest':layer['digest'],'bytes':layer['size']} for layer in manifest['layers']],
            'metadata_only':True,'layers_downloaded':False,'image_built':False,'signature_verified':False,'implicit_volumes':False,'onbuild_triggers':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    try:
        result=resolve()
        with a.output.open('x') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    except (ValueError,OSError,KeyError,http.client.HTTPException):p.exit(2,'Cannot resolve/verify bounded official image metadata; no image pulled or output replaced.\n')
    print(json.dumps({'base_image':result['base_image'],'compressed_layer_bytes':result['compressed_layer_bytes'],'metadata_only':True}))

if __name__=='__main__':main()
