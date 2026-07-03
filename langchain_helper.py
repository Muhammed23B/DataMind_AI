from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from langchain.chains import create_sql_query_chain
from langchain.prompts import FewShotPromptTemplate
from langchain.prompts.prompt import PromptTemplate
from langchain.prompts import SemanticSimilarityExampleSelector
from langchain_community.vectorstores import Chroma
from langchain.chains.sql_database.prompt import PROMPT_SUFFIX

# ✅ Embeddings
from langchain_huggingface import HuggingFaceEmbeddings

# ✅ Standard Libraries
import re

# ✅ Optional (if you use MySQL or need ORM-level control)
import pymysql
from sqlalchemy import create_engine


from few_shots import few_shots

import os
from dotenv import load_dotenv
load_dotenv()  # take environment variables from .env (especially openai api key)


def get_few_shot_db_chain(question : str):
    db_user = "root"
    db_password = "root"
    db_host = "localhost"
    db_name = "atliq_tshirts"

    db = SQLDatabase.from_uri(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}",
                              sample_rows_in_table_info=3)
    api_key = os.getenv("GOOGLE_API_KEY")
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=api_key, temperature=0.2)

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    to_vectorize = [" ".join(example.values()) for example in few_shots]
    vectorstore = Chroma.from_texts(to_vectorize, embeddings, metadatas=few_shots)
    example_selector = SemanticSimilarityExampleSelector(
        vectorstore=vectorstore,
        k=2,
    )
    mysql_prompt = """You are a MySQL expert. Given an input question, first create a syntactically correct MySQL query to run, then look at the results of the query and return the answer to the input question.
        Unless the user specifies in the question a specific number of examples to obtain, query for at most {top_k} results using the LIMIT clause as per MySQL. You can order the results to return the most informative data in the database.
        Never query for all columns from a table. You must query only the columns that are needed to answer the question. Wrap each column name in backticks (`) to denote them as delimited identifiers.
        Pay attention to use only the column names you can see in the tables below. Be careful to not query for columns that do not exist. Also, pay attention to which column is in which table.
        Pay attention to use CURDATE() function to get the current date, if the question involves "today".

        Use the following format:

        Question: Question here
        SQLQuery: Query to run with no pre-amble
        SQLResult: Result of the SQLQuery
        Answer: Final answer here

        No pre-amble.
        """

    example_prompt = PromptTemplate(
        input_variables=["Question", "SQLQuery", "SQLResult", "Answer", ],
        template="\nQuestion: {Question}\nSQLQuery: {SQLQuery}\nSQLResult: {SQLResult}\nAnswer: {Answer}",
    )

    few_shot_prompt = FewShotPromptTemplate(
        example_selector=example_selector,
        example_prompt=example_prompt,
        prefix=mysql_prompt,
        suffix=PROMPT_SUFFIX,
        input_variables=["input", "table_info", "top_k"],  # These variables are used in the prefix and suffix
    )
    generate_sql = create_sql_query_chain(llm, db, prompt=few_shot_prompt)

    def clean_sql(s: str) -> str:
        s = s.strip()
        s = re.sub(r"^```(?:sql)?\s*|\s*```$", "", s, flags=re.I | re.M)  # code fences
        s = re.sub(r"^(SQLQuery:|SQL:|Query:)\s*", "", s, flags=re.I)  # prefixes
        m = re.search(r"(?is)\b(SELECT|WITH|UPDATE|INSERT|DELETE)\b.*", s)
        if m:
            s = m.group(0)
        return s.rstrip().rstrip(";") + ";"

    # 4) Ask your question → get SQL
    #question = "How many t-shirts do we have left for Nike in extra small size and white color?"

    raw_sql = generate_sql.invoke({"question": question})
    print("Generated SQL (raw):\n", raw_sql)

    sql = clean_sql(raw_sql)
    print("SQL Executed:\n", sql)

    # 5) Execute the SQL (request structured output)
    result = db.run(sql, fetch="all", include_columns=True)

    # --- extract JUST the number ---
    def extract_number(res):
        # list of dicts: [{'qty_left': 12}]
        if isinstance(res, list) and res and isinstance(res[0], dict):
            return list(res[0].values())[0]
        # list of tuples: [(12,)]
        if isinstance(res, list) and res and isinstance(res[0], (tuple, list)):
            return res[0][0]
        # plain number
        if isinstance(res, (int, float)):
            return res
        # string: parse first number
        m = re.search(r"[-+]?\d*\.?\d+", str(res))
        return int(float(m.group(0))) if m else res

    Answer = extract_number(result)
    return Answer






