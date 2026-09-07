import os
import unittest
from unittest.mock import patch, Mock

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from ai_service.app import main
from ai_service.app.contract_ai import ContractDraftRequest, generate_draft


class ContractAITests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
        main.Base.metadata.create_all(self.engine)
        def session():
            with Session(self.engine) as value:
                yield value
        main.app.dependency_overrides[main.db_session] = session
        with Session(self.engine) as session:
            client = main.Client(name='test',token_hash=main.token_hash('test-token'),plan_code='pro')
            session.add(client); session.commit()
            self.client_id=client.id
        self.http = TestClient(main.app)
        self.env = patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','CONTRACT_AI_MONTHLY_LIMIT':'1'})
        self.env.start()

    def tearDown(self):
        self.http.close()
        main.app.dependency_overrides.clear()
        self.env.stop()
        self.engine.dispose()

    def request(self, **kwargs):
        return self.http.post('/v1/contracts/draft',json={'kind':'Design','scope':'Criar cinco peças'},headers={'Authorization':'Bearer test-token'},**kwargs)

    def test_authentication_validation_and_quota(self):
        self.assertEqual(self.http.post('/v1/contracts/draft',json={'kind':'x','scope':'x'}).status_code,401)
        with patch('ai_service.app.contract_ai.generate_draft',return_value={'title':'Contrato','content':'Rascunho','status':'Rascunho'}):
            self.assertEqual(self.request().status_code,200)
            self.assertEqual(self.request().status_code,429)
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(main.ContractAIUsage.count)),1)
            self.assertEqual(session.scalar(select(main.MonthlyUsage.id)),None)
        response=self.http.post('/v1/contracts/draft',json={'kind':'x','scope':'x','client_id':99},headers={'Authorization':'Bearer test-token'})
        self.assertEqual(response.status_code,422)

    def test_failure_refunds_and_missing_configuration(self):
        with patch('ai_service.app.contract_ai.generate_draft',side_effect=RuntimeError('Falha controlada')):
            self.assertEqual(self.request().status_code,503)
        with Session(self.engine) as session:
            self.assertEqual(session.scalar(select(main.ContractAIUsage.count)),0)
        with patch.dict(os.environ,{'CONTRACT_AI_MONTHLY_LIMIT':'0'}):
            self.assertEqual(self.request().status_code,503)

    def test_quota_is_per_authenticated_client(self):
        with Session(self.engine) as session:
            session.add(main.Client(name='second',token_hash=main.token_hash('second-token'),plan_code='pro'))
            session.commit()
        with patch('ai_service.app.contract_ai.generate_draft',return_value={'title':'Contrato','content':'Rascunho','status':'Rascunho'}):
            self.assertEqual(self.request().status_code,200)
            response=self.http.post('/v1/contracts/draft',json={'kind':'x','scope':'x'},headers={'Authorization':'Bearer second-token'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(self.request().status_code,429)
    def test_provider_structured_response_and_no_tools(self):
        response=Mock(ok=True)
        response.json.return_value={'output_text':'{"title":"Contrato","content":"Olá {{cliente_nome}}"}'}
        with patch('ai_service.app.contract_ai.requests.post',return_value=response) as call:
            result=generate_draft(ContractDraftRequest(kind='Design',scope='Escopo'))
            body=call.call_args.kwargs['json']
            self.assertFalse(body['store'])
            self.assertNotIn('tools',body)
            self.assertEqual(result['status'],'Rascunho')
        response.json.return_value={'output_text':'invalido'}
        with patch('ai_service.app.contract_ai.requests.post',return_value=response),self.assertRaises(RuntimeError):
            generate_draft(ContractDraftRequest(kind='Design',scope='Escopo'))
