import os
import sys
import pytest
from dotenv import load_dotenv

# Reconfigure stdout to support unicode/emojis in terminal prints
try:
    sys.stdout.reconfigure(encoding='utf-8')
except AttributeError:
    pass

# Load environment variables
load_dotenv()

from deepeval import assert_test
from deepeval.test_case import LLMTestCase, SingleTurnParams
from deepeval.metrics import FaithfulnessMetric, GEval
from deepeval.models.base_model import DeepEvalBaseLLM
from langchain_openrouter import ChatOpenRouter

from config import load_config
from graph import analyze_and_narrate_node, GraphState

# ---------------------------------------------------------------------------
# Custom DeepEval LLM Wrapper for OpenRouter
# This allows us to use your existing OpenRouter API key and Gemini Flash model
# for running evaluations without requiring an OpenAI API key.
# ---------------------------------------------------------------------------
class OpenRouterLLM(DeepEvalBaseLLM):
    def __init__(self, model_name="google/gemini-flash-1.5", api_key=None):
        self.model_name = model_name
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required.")
        self.model = None

    def load_model(self):
        if self.model is None:
            self.model = ChatOpenRouter(
                model_name=self.model_name,
                openrouter_api_key=self.api_key,
                max_retries=1
            )
        return self.model

    def generate(self, prompt: str) -> str:
        model = self.load_model()
        response = model.invoke(prompt)
        return response.content

    async def a_generate(self, prompt: str) -> str:
        model = self.load_model()
        response = await model.ainvoke(prompt)
        return response.content

    def get_model_name(self) -> str:
        return self.model_name


# ---------------------------------------------------------------------------
# Test Definition
# ---------------------------------------------------------------------------
def test_tech_domain_narration():
    # 1. Load settings/configs
    config = load_config()
    
    # 2. Mock input state representing curated articles from RSS
    mock_curated_articles = [
        {
            "domain": "Tech & AI",
            "emoji": "💻",
            "title": "OpenAI Launches GPT-5 with Reasoning",
            "link": "https://techcrunch.com/openai-gpt5",
            "summary": (
                "OpenAI officially announced GPT-5 today. The model features advanced "
                "multi-step reasoning, an expanded context window of 200k tokens, "
                "and significantly improved mathematics and coding performance. "
                "It is rolling out starting today for ChatGPT Plus subscribers."
            )
        }
    ]
    
    state: GraphState = {
        "config": config,
        "raw_articles": [],
        "filtered_articles": [],
        "curated_articles": mock_curated_articles,
        "domain_briefings": {},
        "final_briefing": "",
        "sports_scores": "",
    }
    
    # 3. Execute the narration node to get actual LLM generation
    print("\n-> Running analyze_and_narrate_node for 'Tech & AI'...")
    output_state = analyze_and_narrate_node(state)
    actual_output = output_state["domain_briefings"]["Tech & AI"]
    print(f"\n--- LLM Output ---\n{actual_output}\n------------------")
    
    # 4. Instantiate our evaluation model
    eval_model = OpenRouterLLM(model_name="deepseek/deepseek-chat")
    
    # 5. Define Evaluation Metrics
    
    # Faithfulness: Ensure output does not contain hallucinations/factual inconsistencies
    faithfulness_metric = FaithfulnessMetric(threshold=0.6, model=eval_model)
    
    # G-Eval: Custom metric to check for Gen-Z tone, analogies, and format constraints
    genz_tone_metric = GEval(
        name="Gen-Z Tone & Layout Formatting",
        criteria=(
            "Assess whether the output adheres to the requested tone guidelines and format structure:\n"
            "- Tone should be informal, texting-style, conversational, and humorous (appealing to 18-25 age group).\n"
            "- It should explain concepts using analogies and avoid unexplained technical jargon.\n"
            "- Format constraints:\n"
            "  1. Must start with the domain tag like '--- [💻 TECH & AI]'\n"
            "  2. Followed by a casual headline (maximum 10 words)\n"
            "  3. Followed by a short paragraph (5-6 lines) explaining the news and its impact\n"
            "  4. Followed by a 1-line 'Why it matters to your future: ...'\n"
            "  5. Followed by 'Read more: [exact link]' and ending line '---'"
        ),
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        evaluation_steps=[
            "Verify that the section starts with '--- [💻 TECH & AI]'.",
            "Verify that the headline is simple, conversational, and has no more than 10 words.",
            "Verify that the main body explaining what happened is approximately 5-6 lines and uses a personal/conversational tone.",
            "Verify that the 'Why it matters' line starts with 'Why it matters to your future: '.",
            "Verify that the exact link 'https://techcrunch.com/openai-gpt5' is included in 'Read more: ...'.",
            "Verify that the output concludes with the separator line '---'."
        ],
        threshold=0.7,
        model=eval_model
    )
    
    # 6. Setup DeepEval test case
    test_case = LLMTestCase(
        input=mock_curated_articles[0]["summary"],
        actual_output=actual_output,
        # The raw feed summary and title serve as the retrieval source/truth for the briefing
        retrieval_context=[
            f"Title: {mock_curated_articles[0]['title']}\nSummary: {mock_curated_articles[0]['summary']}"
        ]
    )
    
    # 7. Run metrics validation
    assert_test(test_case, [faithfulness_metric, genz_tone_metric])
