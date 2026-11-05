"""Use the running DeepTutor authentication and workspace contracts."""
from __future__ import annotations
import os
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException,Request

BASE=os.environ.get('WORKBENCH_NATIVE_URL','http://127.0.0.1:8008').rstrip('/')
ORIGIN=os.environ.get('WORKBENCH_ORIGIN','https://tutor.example.invalid')


def headers(request:Request):
    result={'Origin':ORIGIN,'Cookie':request.headers.get('cookie','')}
    if request.headers.get('authorization'):result['Authorization']=request.headers['authorization']
    return result


async def call(request:Request,method,path,**kwargs):
    async with httpx.AsyncClient(timeout=45,trust_env=False) as client:
        response=await client.request(method,BASE+path,headers=headers(request),**kwargs)
    if not response.is_success:
        try:detail=response.json().get('detail','原生服务暂不可用')
        except Exception:detail='原生服务暂不可用'
        raise HTTPException(response.status_code,detail)
    return response.json()


async def text_call(request:Request,path):
    async with httpx.AsyncClient(timeout=45,trust_env=False) as client:
        response=await client.get(BASE+path,headers=headers(request))
    if not response.is_success:raise HTTPException(response.status_code,'原生文献文本暂不可用')
    if 'json' in response.headers.get('content-type',''):
        value=response.json();return value.get('text') or value.get('content') or ''
    return response.text


async def actor(request:Request):
    profile=await call(request,'GET','/api/auth/profile')
    if not profile.get('id'):raise HTTPException(401,'请先登录 DeepTutor')
    if request.method not in ('GET','HEAD','OPTIONS'):
        source=request.headers.get('origin')
        if source and source.rstrip('/')!=ORIGIN:raise HTTPException(403,'请求来源与工作台不一致')
    return profile
