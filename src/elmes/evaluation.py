import csv
import json
import re
from typing import Any, Dict
from pathlib import Path
from langchain_core.tools import tool, BaseTool
from elmes.config import CONFIG
from langgraph.prebuilt import create_react_agent
from langchain.chat_models.base import BaseChatModel
from elmes.entity import ExportFormat
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_fixed


def _serialize_log_value(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump()
    elif hasattr(value, "model_dump"):
        value = value.model_dump()
    elif hasattr(value, "dict"):
        value = value.dict()

    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _append_prompt_log(
    config: Any,
    original_system_prompt: str,
    original_other_prompts_formatted: str,
    original_other_prompts: list[str],
    final_system_prompt: str,
    argv_last: str,
    final_other_prompts_formatted: str,
    ops: list[dict[str, Any]],
    response: str,
) -> None:
    log_dir = Path(__file__).resolve().parent / "log"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "evaluation_prompt_log.csv"
    file_exists = log_file.exists()

    with log_file.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(
                [
                    "CONFIG",
                    "original_system_prompt",
                    "original_other_prompts_formatted",
                    "original_other_prompts",
                    "final_system_prompt",
                    "sys.argv[-1]",
                    "final_other_prompts_formatted",
                    "final_other_prompts",
                    "response",
                ]
            )
        writer.writerow(
            [
                _serialize_log_value(config),
                original_system_prompt,
                original_other_prompts_formatted,
                _serialize_log_value(original_other_prompts),
                final_system_prompt,
                argv_last,
                final_other_prompts_formatted,
                _serialize_log_value(ops),
                response,
            ]
        )


def generate_evaluation_tool() -> BaseTool:
    """
    Generates a tool for evaluating the Elmes evaluation framework.
    This function is a placeholder and should be implemented with actual logic.
    """

    if CONFIG.evaluation is None:
        raise ValueError("Evaluation configuration not found.")

    @tool(
        name_or_callable="save_result_to_database",
        description="Save the evaluation results to a database.",
        return_direct=True,
        args_schema=CONFIG.evaluation.format_to_pydantic(),
    )
    def save_to_db(**kwargs):
        """
        Save the evaluation results to a database.
        """
        for k, v in kwargs.items():
            if issubclass(v.__class__, BaseModel):
                v = v.model_dump()
            kwargs[k] = v
        return kwargs

    return save_to_db


@retry(
    stop=stop_after_attempt(CONFIG.globals.retry.attempt),
    wait=wait_fixed(CONFIG.globals.retry.interval),
)
async def evaluate(
    model: BaseChatModel, exported_result: ExportFormat
) -> Dict[str, Any]:
    # sample: exported_result
    # ExportFormat(task={'image': '小学二年级，女生', 'query': '下节课学习有理数，你帮我预习'}, messages=[Prompt(role='teacher', content='老师真为你这入初中才会遇到的新朋友，我们现在先把正数的基础打牢好不好？')])

    assert CONFIG.evaluation
    system_prompt, other_prompt = CONFIG.evaluation.get_prompts()
    original_system_prompt = system_prompt
    system_prompt = exported_result.replace_template(system_prompt)
    # **************************************************
    # 你是一个有多年小学数学教学经验的标注员。我给你一段【输入文本】，这是AI数学老师给一个小学生讲解知识点的文本。你针对【学生画像】【学生需求】和【评分规则】【评分标准】，对【输入文本】进行评分。
    #
    # ##评分规则##
    # 每个评分标准的满分是10分，你给出1-10的评分。评分只能是整数。对完全满足评价标准的，你才能给出10分。对完全不符合评分标准的，你的评分低于5分。
    #
    # ##评分标准##
    # -角色贴合性-：
    # 1.表现出符合[小学数学老师]的知识储备、语言风格和性格特质。按照[小学数学老师]的口吻，从第一人称的口吻叙述。
    # 2.不出现“同学们”“有些同学”这种不符合“一对一”教学场景的称呼。
    # 3.不尝试与学生进行任何物理互动，也不描述任何自己的表情、动作、行为，更不会介绍自己的教学设计，没有任何如“（等待学生回答后）”“（如果学生回答正确）……”这一类是“教学助手”而非“教师”的行为。
    # -情感支持性-：对学生表现出赞同与肯定，给学生充分的、积极的情感支持。
    # -知识点掌握程度-：对小学的知识点的内容有充分的理解，能进行正确、恰当的介绍。
    # -教学方法合理性-：教学的步骤和逻辑合乎常理；能反问学生的一些观点；没有直接告诉学生答案，而是先引导学生思考，在恰当的时候给学生提供新的信息，引导学生进行深入的思考。
    # -内容设计合理性-：不使用任何超过小学生认知的事物举例。教学内容涉及真实的生活场景，鼓励小学生用数学解决生活问题。
    # -用户特征呼应-：对【学生画像】中的信息有所呼应。
    #
    # ##学生画像##
    # 小学二年级，女生
    #
    # ##学生需求##
    # 下节课学习有理数，你帮我预习
    #
    # ##输入文本##
    # teacher: 老师真为你这份提前学习的热情点赞，不过有理数里神奇的负数知识是等你升入初中才会遇到的新朋友，我们现在先把正数的基础打牢好不好？
    #
    # ^^^(system_prompt)^^^
    #
    # at:
    # src/elmes/evaluation.py:54
    # **************************************************

    print('*' * 50 + f'''\n{system_prompt}\n^^^(system_prompt)^^^\n''' + '''\nat:\nsrc/elmes/evaluation.py:54\n''' + '*' * 50)


    # import pdb
    # pdb.set_trace()

    original_other_prompts = []
    final_other_prompts = []

    for op in other_prompt:
        original_other_prompts.append(op.content)

        content = exported_result.replace_template(op.content)
        final_other_prompts.append(
            {
                "role": op.role,
                "content": content,
            }
        )

    original_other_prompts_formatted = '''
    ---
    '''.join(
            original_other_prompts
    )
    if CONFIG.evaluation.format_mode == "tool":
        tools = [generate_evaluation_tool()]

        # other_prompt = exported_result.replace_template(other_prompt)
        agent = create_react_agent(
            model=model.bind_tools(
                tools,
                tool_choice={
                    "type": "function",
                    "function": {"name": "save_result_to_database"},
                },  # type: ignore
                # tool_choice="required",
            ),
            tools=tools,
            # model=model,
            prompt=system_prompt
            + "\n\n请调用save_result_to_database工具以将评估结果存入数据库",
        )

        a = await agent.ainvoke({"messages": final_other_prompts})
        data = json.loads(a["messages"][-1].content)
        return data
    elif CONFIG.evaluation.format_mode == "prompt":
        import sys
        argv_last = sys.argv[-1] if sys.argv else ""
        final_system_prompt  = (system_prompt
            + "\n\n# NOTE！\n\n"
            + "You should keep your output in the following JSON format blow, and wrap it with exactlly <START OF EVAL OUTPUT> and <END OF EVAL OUTPUT> ONLY!, no escape.\n\n".upper()
            + f"\n\njson schema:\n\n\n{CONFIG.evaluation.format_to_json_schema()}\n\n\n"
            + "\n\nFORMAT EXAMPLE:\n\n"
            + "\n\n<START OF EVAL OUTPUT>\n\n"
            # + "```json"
            + f"{CONFIG.evaluation.format_to_json_example()}\n"
            # + "```"
            + "<END OF EVAL OUTPUT>")
        agent = create_react_agent(
            model=model,
            tools=[],
            prompt=final_system_prompt ,
        )
        print('*' * 50 + f'''\n{final_other_prompts}\n^^^(final_other_prompts)^^^\n''' + '''\nat:\nsrc/elmes/evaluation.py:98\n''' + '*' * 50)
        # **************************************************
        # [{'role': 'user', 'content': '请你评估\n'}]
        # ^^^(final_other_prompts)^^^
        #
        # at:
        # src/elmes/evaluation.py:98
        # **************************************************
        a = await agent.ainvoke({"messages": final_other_prompts})
        # sample output:
        # **************************************************
        #
        #
        # <START OF EVAL OUTPUT>
        # {"角色贴合性":9,"情感支持性":9,"知识点掌握程度":10,"教学方法合理性":9,"内容设计合理性":9,"用户特征呼应":8}
        # <END OF EVAL OUTPUT>
        # ^^^(response)^^^
        #
        # at:
        # src/elmes/evaluation.py:101
        # **************************************************
        final_other_prompts_formatted = '''
        ---
        '''.join(
            [op["content"] for op in final_other_prompts]
        )
        response: str = a["messages"][-1].content
        _append_prompt_log(
            CONFIG,
            original_system_prompt,
            original_other_prompts_formatted,
            original_other_prompts,
            final_system_prompt,
            argv_last,
            final_other_prompts_formatted,
            final_other_prompts,
            response,
        )
        print('*' * 50 + f'''\n{response}\n^^^(response11)^^^\n''' + '''\nat:\nsrc/elmes/evaluation.py:101\n''' + '*' * 50)


        # Fuck Gemini
        response = response.replace("\\<", "<")
        response = response.replace("\\>", ">")

        # print(response)

        # 正则表达式匹配<START OUTPUT>和<END OUTPUT>
        match = re.findall(
            r"<START OF EVAL OUTPUT>(.*)<END OF EVAL OUTPUT>", response, re.DOTALL
        )
        if len(match) > 0:
            text = match[-1]
            # 如果text被```包围，去掉
            text = text.strip().strip("```").strip("json")
            # print(text, "#############")
            return json.loads(text)
        else:
            raise ValueError("Output does not contain <START OUTPUT> and <END OUTPUT>")
    else:
        raise ValueError(f"Invalid format mode: {CONFIG.evaluation.format_mode}")


if __name__ == "__main__":
    import asyncio

    async def main():
        from elmes.model import init_chat_model_from_dict
        # from langchain.globals import set_debug

        # set_debug(True)

        ef = ExportFormat.from_json_file(
            "/Users/mars160/elmes/guided_teaching/4f699a38-33fe-4cd6-8013-06e191e249ab.json"
        )

        model = init_chat_model_from_dict(CONFIG.models["4o_teacher"])
        a = await evaluate(model, ef)
        print(a)

    asyncio.run(main())
