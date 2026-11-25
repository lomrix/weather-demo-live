"""One-action local-model budget and fail-closed response checks.

Token ceilings are supplied to Ollama's documented options. Byte/request limits
are enforced in Python. Reported token overruns reject the response; they do
not retroactively cancel computation already performed by the model server.
"""
import json
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

ENDPOINT='http://127.0.0.1:11434/api/generate'
CONTEXT_TOKENS=4096
GENERATED_TOKENS=700
PROMPT_BYTES=12*1024
RESPONSE_BYTES=16*1024
BODY_BYTES=32*1024


class BudgetStop(RuntimeError):
    def __init__(self,message,requests_made=0):
        super().__init__(message);self.requests_made=requests_made


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise BudgetStop('Model redirects are not permitted',requests_made=1)


class LocalModelRun:
    def __init__(self,opener=urlopen):
        self.opener=build_opener(NoRedirect()).open if opener is urlopen else opener
        self.requests_started=0;self.generated_limit=GENERATED_TOKENS

    def open(self,request,timeout):
        if self.requests_started:
            raise BudgetStop('Model run stopped: one-request budget exhausted',self.requests_started)
        if request.full_url!=ENDPOINT or request.get_method()!='POST':
            raise BudgetStop('Model run stopped: only the fixed local Ollama endpoint is permitted')
        if not request.data or len(request.data)>BODY_BYTES:
            raise BudgetStop('Model run stopped: request body budget exceeded')
        body=json.loads(request.data)
        prompt=body.get('prompt')
        if not isinstance(prompt,str) or len(prompt.encode('utf-8'))>PROMPT_BYTES:
            raise BudgetStop('Model run stopped: prompt byte budget exceeded')
        options=body.get('options',{})
        limit=options.get('num_predict',GENERATED_TOKENS)
        if isinstance(limit,bool) or not isinstance(limit,int) or not 1<=limit<=GENERATED_TOKENS:
            raise BudgetStop('Model run stopped: generation budget must be 1–700 tokens')
        self.generated_limit=limit
        body['options']={**options,'num_ctx':CONTEXT_TOKENS,'num_predict':limit}
        body['stream']=False
        forwarded=Request(ENDPOINT,data=json.dumps(body).encode('utf-8'),headers={'Content-Type':'application/json'},method='POST')
        self.requests_started=1
        response=self.opener(forwarded,timeout=timeout)
        return BudgetResponse(response,self)


class BudgetResponse:
    def __init__(self,response,run):self.response=response;self.run=run
    def __enter__(self):self.response.__enter__();return self
    def __exit__(self,*args):return self.response.__exit__(*args)
    def read(self,limit):
        raw=self.response.read(min(limit,RESPONSE_BYTES+1))
        if len(raw)>RESPONSE_BYTES:
            raise BudgetStop('Ollama response exceeded the size limit',1)
        try:envelope=json.loads(raw)
        except ValueError:return raw  # Normal schema validation reports malformed JSON.
        if not isinstance(envelope,dict):return raw
        for field,maximum in (('prompt_eval_count',CONTEXT_TOKENS),('eval_count',self.run.generated_limit)):
            value=envelope.get(field)
            if value is not None and (isinstance(value,bool) or not isinstance(value,int) or not 0<=value<=maximum):
                raise BudgetStop('Model run stopped: reported token usage exceeded its budget',1)
        return raw


def policy():
    return {'requests_per_action':1,'context_tokens':CONTEXT_TOKENS,'generated_tokens':GENERATED_TOKENS,
            'prompt_bytes':PROMPT_BYTES,'response_bytes':RESPONSE_BYTES,
            'endpoint':ENDPOINT,'automatic_retries':0,
            'enforcement_scope':'Python enforces bytes, endpoint and request count; Ollama enforces configured token options. Reported overruns are rejected.'}
