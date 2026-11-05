"""Run the installed upstream Scholar MCP with explicit challenge detection."""
import re
from scholar_mcp import server
from scholar_mcp.scholar_client import ScholarClientError


def verify_response(response,*args,**kwargs):
    body=response.text[:500000]
    challenge=('/sorry/' in response.url or re.search(r'our systems have detected unusual traffic|gs_captcha|g-recaptcha|name=["\']captcha|verify (?:that )?you are (?:a )?human',body,re.I))
    consent='consent.google.' in response.url and 'gs_r' not in body
    if challenge or consent:raise ScholarClientError('verification_required','Google Scholar requires manual verification or consent in its own browser. No challenge was solved automatically.',False)


server.client.session.hooks['response'].append(verify_response)
server.main()
