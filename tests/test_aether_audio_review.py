from __future__ import annotations
import base64,json
from pathlib import Path
import sys,tempfile,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import aether_audio_review as review

class Response:
    def __init__(self,payload): self.payload=payload
    def __enter__(self): return self
    def __exit__(self,*args): return False
    def read(self,size): return self.payload[:size]

def accepted_doc():
    return {"decision":"accept","scores":{
        "aether_fit":8,"melody_memorability":8,"repeat_listening_comfort":8,
        "arrangement_development":7,"ending_resolution":9,"technical_cleanliness":9},
        "flags":{"overly_ambient":False,"aggressive_percussion":False,
        "edm_or_pop_energy":False,"trailer_bombast":False,"sharp_high_piano":False,
        "unresolved_ending":False,"unexpected_vocals":False,"technical_artifact":False},
        "reason_codes":[]}

class ReviewTests(unittest.TestCase):
    def test_unresolved_ending_cannot_be_accepted(self):
        doc=accepted_doc();doc["flags"]["unresolved_ending"]=True
        self.assertFalse(review.validate(doc)["accepted"])

    def test_thresholds_fail_closed(self):
        doc=accepted_doc();doc["scores"]["aether_fit"]=6
        self.assertFalse(review.validate(doc)["accepted"])

    def test_request_contains_actual_audio_and_json_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/"song.mp3";path.write_bytes(b"x"*2048)
            body_seen={}
            payload=json.dumps({"candidates":[{"content":{"parts":[
                {"text":json.dumps(accepted_doc())}]}}]}).encode()
            def send(req):
                body_seen.update(json.loads(req.data));return Response(payload)
            with patch.object(review,"load_settings",return_value={"project_id":"aether-music-123"}):
                result=review.review_audio(path,"Title","Style","skybound_flight",token="token",send=send)
            self.assertTrue(result["accepted"])
            parts=body_seen["contents"][0]["parts"]
            self.assertEqual("audio/mpeg",parts[1]["inlineData"]["mimeType"])
            self.assertEqual("application/json",body_seen["generationConfig"]["responseMimeType"])

    def test_unknown_reason_rejected(self):
        doc=accepted_doc();doc["reason_codes"]=["made_up"]
        with self.assertRaises(Exception): review.validate(doc)

if __name__=="__main__":unittest.main()
