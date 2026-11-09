import unittest
from unittest.mock import Mock, patch
from agent import cloudflare_photos as c


class CloudflareDiagnosticsTests(unittest.TestCase):
    def test_structured_bad_request_shows_reason(self):
        response=Mock(status_code=400)
        response.json.return_value={
            'success':False,
            'errors':[{'code':5006,'message':"AiError: Bad input: required properties at '/' are 'multipart'"}]
        }
        msg=c._safe_provider_error(response,'a'*32,'my-private-token')
        self.assertIn('5006',msg)
        self.assertIn('multipart',msg)
        self.assertNotIn('my-private-token',msg)

    def test_redacts_secret_and_email_even_when_provider_echoes(self):
        secret='cfut_fake-secret-123'
        account='b'*32
        response=Mock(status_code=400)
        response.json.return_value={'errors':[{'code':123,'message':
            'Token '+secret+' Bearer '+secret+' account '+account+' user@example.org'}]}
        msg=c._safe_provider_error(response,account,secret)
        self.assertNotIn(secret,msg)
        self.assertNotIn(account,msg)
        self.assertNotIn('user@example.org',msg)
        self.assertIn('[REDACTED]',msg)

    def test_nonjson_error_still_usable(self):
        response=Mock(status_code=400)
        response.json.side_effect=ValueError('Not JSON')
        msg=c._safe_provider_error(response,'a'*32,'fake-token-secret')
        self.assertIn('No details provided',msg)

    def test_cloudflare_http_400_surfaces_details(self):
        from pathlib import Path
        label=next(iter(c.MODELS))
        response=Mock(status_code=400,ok=False)
        response.json.return_value={'errors':[{'code':5020,'message':'Input image is too large'}]}
        with patch.object(c,'reference_png',return_value=b'png'),patch.object(c.requests,'post',return_value=response):
            with self.assertRaises(ValueError) as exc:
                c.generate(Path('any.png'),'straight_front','a'*32,'private-fake-token',label)
        self.assertIn('5020',str(exc.exception))
        self.assertIn('too large',str(exc.exception))
        self.assertNotIn('private-fake-token',str(exc.exception))

if __name__=='__main__':
    unittest.main()
