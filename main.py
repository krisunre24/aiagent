import argparse
import os
import sys
from dotenv import load_dotenv
from openai import OpenAI

from prompts import system_prompt
from call_function import available_functions, call_function
from logger import start_run, record_iteration, finish_run


def main():
    load_dotenv()
    api_key = os.environ.get("OPENROUTER_API_KEY")

    if api_key is None:
        raise RuntimeError(
            "OPENROUTER_API_KEY not found. Make sure you have a .env file with OPENROUTER_API_KEY set."
        )

    parser = argparse.ArgumentParser(description="Chatbot")
    parser.add_argument("user_prompt", type=str, help="User prompt")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    parser.add_argument("--model", type=str, default="openrouter/free", help="OpenRouter model ID")
    args = parser.parse_args()

    working_directory = os.environ.get("AGENT_WORKING_DIR", "./calculator")

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=api_key,
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": args.user_prompt},
    ]

    if args.verbose:
        print(f"User prompt: {args.user_prompt}")

    run = start_run(
        task_id=args.user_prompt[:40].replace(" ", "_"),
        model=args.model,
        user_prompt=args.user_prompt,
    )

    for _ in range(20):
        try:
            response = client.chat.completions.create(
                model=args.model,
                messages=messages,
                tools=available_functions,
                temperature=0,
            )
        except Exception as e:
            finish_run(run, success=False, error=f"API_ERROR: {e}")
            print(f"API_ERROR: {e}")
            sys.exit(2)

        if response.usage is None:
            finish_run(run, success=False, error="No usage data returned from API")
            raise RuntimeError("No usage data returned from the API — the request may have failed.")

        message = response.choices[0].message
        messages.append(message)

        tool_call_names = [tc.function.name for tc in message.tool_calls] if message.tool_calls else []
        record_iteration(
            run,
            prompt_tokens=response.usage.prompt_tokens,
            completion_tokens=response.usage.completion_tokens,
            tool_call_names=tool_call_names,
        )

        if args.verbose:
            print(f"Prompt tokens: {response.usage.prompt_tokens}")
            print(f"Response tokens: {response.usage.completion_tokens}")

        if not message.tool_calls:
            print("Final response:")
            print(message.content)
            finish_run(run, success=True, final_response=message.content)
            return

        for tool_call in message.tool_calls:
            result_message = call_function(tool_call, working_directory, verbose=args.verbose)
            if not result_message.get("content"):
                finish_run(run, success=False, error=f"Function {tool_call.function.name} returned no content")
                raise Exception(f"Function {tool_call.function.name} did not return content")
            if args.verbose:
                print(f"-> {result_message['content']}")
            messages.append(result_message)

    print("Error: Maximum iterations reached without a final response.")
    finish_run(run, success=False, error="Max iterations reached")
    sys.exit(1)


if __name__ == "__main__":
    main()
