"""
ReActエージェント Function App
シンプルなHTTPトリガーでエージェントループを実行
"""
import azure.functions as func
import json
import logging
from agent_loop import agent_loop

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.route(route="ask", methods=["POST"])
def ask_agent(req: func.HttpRequest) -> func.HttpResponse:
    """
    ReActエージェントに質問を投げる

    Request Body:
    {
        "user_query": "切削オーバーレイ8000m2、殻運搬、区画線工を含む関東の工事を教えて",
        "max_iterations": 10
    }

    Response:
    {
        "status": "completed",
        "iterations": 5,
        "final_answer": "...",
        "thinking_history": [...]
    }
    """
    logging.info("ReAct agent request received")

    try:
        req_body = req.get_json()
        logging.info(f"Request body: {json.dumps(req_body, ensure_ascii=False)[:500]}")
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json"
        )

    user_query = req_body.get("user_query", "")
    if not user_query:
        return func.HttpResponse(
            json.dumps({"error": "user_query is required"}, ensure_ascii=False),
            status_code=400,
            mimetype="application/json"
        )

    max_iterations = req_body.get("max_iterations", 10)

    try:
        result = agent_loop({
            "user_query": user_query,
            "max_iterations": max_iterations
        })

        return func.HttpResponse(
            json.dumps(result, ensure_ascii=False, indent=2),
            status_code=200,
            mimetype="application/json"
        )
    except Exception as e:
        logging.error(f"Agent loop error: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json"
        )


@app.route(route="health", methods=["GET"])
def health_check(req: func.HttpRequest) -> func.HttpResponse:
    """ヘルスチェックエンドポイント"""
    return func.HttpResponse(
        json.dumps({"status": "healthy", "service": "react-agent"}),
        status_code=200,
        mimetype="application/json"
    )
