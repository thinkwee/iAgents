from openai import OpenAI
import os
import yaml
from llama_index.llms.openai_like import OpenAILike
from llama_index.llms.dashscope import DashScope, DashScopeGenerationModels
import qianfan


file_path = os.path.dirname(__file__)
project_path = os.path.dirname(file_path)
global_config = yaml.safe_load(open(os.path.join(project_path, "config/global.yaml"), "r"))

DEEPSEEK_API_KEY = global_config.get("backend").get("deepseek_api_key")
QWEN_API_KEY = global_config.get("backend").get("qwen_api_key")
QIANFAN_ACCESS_KEY = global_config.get("backend").get("QIANFAN_ACCESS_KEY")
QIANFAN_SECRET_KEY = global_config.get("backend").get("QIANFAN_SECRET_KEY")
GLM_API_KEY = global_config.get("backend").get("glm_api_key")
HUNYUAN_API_KEY = global_config.get("backend").get("hunyuan_api_key")
SPARK_API_KEY = global_config.get("backend").get("spark_api_key")
os.environ["DASHSCOPE_API_KEY"] = QWEN_API_KEY
os.environ["QIANFAN_ACCESS_KEY"] = QIANFAN_ACCESS_KEY
os.environ["QIANFAN_SECRET_KEY"] = QIANFAN_SECRET_KEY

client_deepseek = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
client_deepseek_llama_index = OpenAILike(api_key=DEEPSEEK_API_KEY, api_base="https://api.deepseek.com/beta", model="deepseek-chat")

client_qwen = OpenAI(api_key=QWEN_API_KEY, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1")
client_qwen_llama_index = DashScope(model_name=DashScopeGenerationModels.QWEN_MAX, api_key=QWEN_API_KEY)

client_glm = OpenAI(api_key=GLM_API_KEY, base_url="https://open.bigmodel.cn/api/paas/v4/") 
client_glm_llama_index = OpenAILike(api_key=GLM_API_KEY, api_base="https://open.bigmodel.cn/api/paas/v4/", model="glm-4-flash", is_chat_model=True, is_function_calling_model=False)

client_hunyuan = OpenAI(api_key=HUNYUAN_API_KEY, base_url="https://api.hunyuan.cloud.tencent.com/v1")
client_hunyuan_llama_index = OpenAILike(api_key=HUNYUAN_API_KEY, api_base="https://api.hunyuan.cloud.tencent.com/v1", model="hunyuan-lite", is_chat_model=True, is_function_calling_model=False)

client_spark = OpenAI(api_key=SPARK_API_KEY, base_url='https://spark-api-open.xf-yun.com/v1')
client_spark_llama_index = OpenAILike(api_key=SPARK_API_KEY, api_base='https://spark-api-open.xf-yun.com/v1', model="general", is_chat_model=True, is_function_calling_model=False)

def query_deepseek(prompt):
    response = client_deepseek.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {"role": "user", "content": prompt},
        ],
        stream=False
    )

    return response.choices[0].message.content



def query_qwen(prompt, model="qwen-max-latest"):
    completion = client_qwen.chat.completions.create(
        model=model,
        messages=[
            {'role': 'system', 'content': 'You are a helpful assistant.'},
            {'role': 'user', 'content': prompt}],
        )
        
    return completion.choices[0].message.content


def query_ernie(prompt):
    chat_comp = qianfan.ChatCompletion()

    resp = chat_comp.do(model="ERNIE-Speed-128K", messages=[{
        "role": "user",
        "content": prompt
    }])

    return resp["body"]["result"]


def query_glm(prompt):
    completion = client_glm.chat.completions.create(
        model="glm-4-flash",  
        messages=[    
            {"role": "system", "content": "You are a helpful assistant."},    
            {"role": "user", "content": prompt}],
            top_p=0.7,
            temperature=0.9
        ) 
 
    return completion.choices[0].message.content


def query_hunyuan(prompt):  
    completion = client_hunyuan.chat.completions.create(
        model="hunyuan-lite",
        messages=[
            {
                "role": "user",
                "content": prompt,
            },
        ]
    )
    return completion.choices[0].message.content

def query_spark(prompt):    
    completion = client_spark.chat.completions.create(
        model='general',
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]
    )
    return completion.choices[0].message.content