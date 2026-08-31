"""Optional OpenAI explanation provider; never receives credentials or raw Amazon data."""
import json
class OpenAIExplanationProvider:
    def __init__(self,api_key,model): self._api_key=api_key; self._model=model
    def explain(self,payload):
        from openai import OpenAI
        client=OpenAI(api_key=self._api_key)
        prompt="Explain only the provided deterministic recommendations. Do not invent actions, change action codes or priority, predict sales/profit, claim certainty, or suggest autonomous Amazon writes. Return JSON with headline, summary, overall_action, priority, and action_explanations containing action, priority, explanation.\nDATA:\n"+json.dumps(payload,sort_keys=True)
        response=client.chat.completions.create(model=self._model,messages=[{"role":"system","content":"You are a constrained seller-facing explanation assistant."},{"role":"user","content":prompt}],response_format={"type":"json_object"})
        return json.loads(response.choices[0].message.content or "{}")
