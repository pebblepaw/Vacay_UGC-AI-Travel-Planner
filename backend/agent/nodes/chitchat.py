from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import settings
from backend.agent.state import AgentState

llm = ChatGoogleGenerativeAI(
    model_name="gemini-2.0-flash",
    api_key=settings.GEMINI_API_KEY
)

prompt = ChatPromptTemplate.from_template("You are a friendly travel assistant. Reply to {input}")

chain = prompt | llm

def chitchat_node(state: AgentState): 
    last_msg = state['messages'][-1].content
    response = chain.invoke({'input': last_msg})
    return {'messages': [response]}