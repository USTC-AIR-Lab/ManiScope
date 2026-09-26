import ast
import tokenize
import io
import re


def remove_comments_and_docstrings(source):
    """Remove comments and docstrings from Python source."""
    src = io.StringIO(source)
    out = []
    prev_tok_type = tokenize.INDENT
    last_lineno = -1
    last_col = 0

    for tok in tokenize.generate_tokens(src.readline):
        token_type = tok.type
        token_string = tok.string
        start_line, start_col = tok.start
        end_line, end_col = tok.end

        if start_line > last_lineno:
            out.append("\n" * (start_line - last_lineno - 1))
            last_col = 0
        elif start_col > last_col:
            out.append(" " * (start_col - last_col))

        if token_type == tokenize.COMMENT:
            pass
        elif token_type == tokenize.STRING:
            if prev_tok_type not in (tokenize.INDENT, tokenize.NEWLINE):
                # Identify a docstring.
                if re.match(r'^\s*"""(?:[^"]|"{1,2})*"""$', token_string) or re.match(
                        r"^\s*'''(?:[^']|'{1,2})*'''$", token_string):
                    continue
                else:
                    out.append(token_string)
            else:
                continue
        else:
            out.append(token_string)

        prev_tok_type = token_type
        last_col = end_col
        last_lineno = end_line

    return "".join([i for i in out if i.strip() != ""]).strip()


def get_method_source(filename, method_name):
    """Extract method source from the specified class."""
    with open(filename, "r", encoding="utf-8") as f:
        source = f.read()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Traverse all class methods.
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    lines = source.splitlines(keepends=True)
                    start_line = item.lineno - 1
                    end_line = _get_function_end_line(item, lines)
                    method_source = "".join(lines[start_line:end_line])
                    return method_source

    raise ValueError(f"Method '{method_name}' not found.")


def _get_function_end_line(node, lines):
    last_child = None
    for child in ast.walk(node):
        if hasattr(child, "lineno"):
            if last_child is None or child.lineno > last_child.lineno:
                last_child = child
    if last_child:
        return last_child.lineno
    return node.lineno


def save_to_tmp(method_source, tmp_file="tmp.txt"):
    with open(tmp_file, "w", encoding="utf-8") as f:
        f.write(method_source)


def read_from_new(new_file="new.txt"):
    with open(new_file, "r", encoding="utf-8") as f:
        return f.read()


def normalize_code(code):
    code_no_comments = remove_comments_and_docstrings(code)
    return code_no_comments


def compare_functions(code1, code2):
    normalized1 = normalize_code(code1)
    normalized2 = normalize_code(code2)
    return normalized1 == normalized2


def replace_method_in_file_with_comments(filename, method_name, new_method_source):
    """Replace a class method while preserving surrounding comments and source structure."""
    with open(filename, "r", encoding="utf-8") as f:
        lines = f.readlines()

    with open(filename, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    start_line = item.lineno - 1  # Line numbers are one-based.
                    end_line = _get_function_end_line(item, lines)

                    # Preserve indentation when replacing the method source range, then write the file.

                    new_lines = new_method_source.splitlines(keepends=True)


                    lines[start_line:end_line] = new_lines


                    with open(filename, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    return

    raise ValueError(f"Method '{method_name}' not found.")


system_prompt = """Annotate the supplied Python code without changing executable code. Explain each self.move call in play_once with a concise English comment. self.move accepts up to two per-arm action sequences returned by grasp_actor, place_actor, move_to_pose, move_by_displacement, close_gripper, open_gripper, and back_to_origin. Preserve arguments, ordering, and all existing behavior. Return only the annotated code block."""

import os
import time
import traceback
from openai import OpenAI


def parse(source, max_try=5, verbose=True):
    """Request code annotation."""
    os.environ["all_proxy"] = ""
    os.environ["http_proxy"] = ""
    os.environ["https_proxy"] = ""
    client = OpenAI(api_key="", base_url="")
    start, try_times = time.time(), 0
    while try_times < max_try:
        try_times += 1
        try:
            response = client.chat.completions.create(
                model="deepseek-v3-250324",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": source
                    },
                ],
                stream=True,
            )
            on_thinking, thinking, answering = False, "", ""
            process_count, process = 0, ["|", "/", "-", "\\"]
            for chunk in response:
                content = chunk.choices[0].delta.content
                if content is None:
                    continue
                if hasattr(chunk.choices[0].delta, "reasoning_content"):
                    thinking += chunk.choices[0].delta.reasoning_content
                else:
                    if content == "<think>":
                        on_thinking = True
                    elif content == "</think>":
                        on_thinking = False
                    elif on_thinking:
                        thinking += content
                    else:
                        answering += content

                if verbose:
                    process_count = (process_count + 1) % 4
                    process_show = (thinking + answering)[-50:].replace("\n", "")
                    print(f'\r  {" "*100}', end="")
                    print(f"\r{process[process_count]} {process_show}", end="", flush=True)
        except SyntaxError:
            print(traceback.format_exc())
            break
        except:
            print(traceback.format_exc())
            continue

        result = re.search(r"```python\n([\s\S]*?)\n```", answering, re.S)
        if result is not None:
            if verbose:
                print(
                    f"cost {time.time()-start:.2f}s, try {try_times} time(s)",
                    flush=True,
                )
            return result.group(1)
    return None


def main(file_path, max_try=5, verbose=True):
    try_count = 0
    while try_count < max_try:
        try_count += 1
        # Step 1: extract class methods.
        method_source = get_method_source(file_path, "play_once")

        # Step 2: request code analysis.
        processed_source = parse(method_source, max_try=5, verbose=verbose)

        # Step 3: compare methods.
        if compare_functions(method_source, processed_source):
            replace_method_in_file_with_comments(file_path, "play_once", processed_source)
            break

    if try_count >= max_try:
        with open("error.log", "a", encoding="utf-8") as f:
            f.write(f"Error processing {file_path}: Exceeded maximum retries.\n")


from threading import Thread
from pathlib import Path


def batch(batch_size=5, root="./envs"):
    name_list = [
        "beat_block_hammer",
        "blocks_ranking_rgb",
        "blocks_ranking_size",
        "dump_bin_bigbin",
        "grab_roller",
        "lift_pot",
        "move_can_pot",
        "move_playingcard_away",
        "move_stapler_pad",
        "place_a2b_left",
        "place_a2b_right",
        "place_bread_basket",
        "place_bread_skillet",
        "place_can_basket",
        "place_cylinder_box",
        "place_fan",
        "place_medicine_spot",
        "place_mouse_pad",
        "place_object_scale",
        "place_object_stand",
        "place_phone_stand",
        "place_remote_storage",
        "place_object_basket",
        "put_bottles_dustbin",
        "rotate_qrcode",
        "shake_bottle",
        "shake_bottle_horizontally",
        "place_shoe",
        "slide_mouse_pad",
        "stamp_seal",
        "handover_block",
        "stack_blocks_three",
        "stack_blocks_two",
        "adjust_bottle",
        "stack_bowls_three",
        "stack_bowls_two",
        "click_alarmclock",
        "click_bell",
        "place_container_plate",
        "pick_diverse_bottles",
        "pick_dual_bottles",
        "place_dual_shoes",
        "place_empty_cup",
        "place_object_into_plasticbox",
    ]
    process_list = []
    for file in name_list:
        file = Path(root) / f"{file}.py"
        if file.exists():
            process_list.append(file)
        else:
            print(f"WARNNING: {file.name} not exists!")

    # Create and start a thread for each file
    threads = []
    finish_count, total_count = 0, len(process_list)
    for file in process_list:
        thread = Thread(target=main, args=(file, 5, False))
        thread.start()
        threads.append([file, thread])
        while len(threads) >= batch_size:
            for t in threads:
                if not t[1].is_alive():
                    threads.remove(t)
                    finish_count += 1
                    print(
                        f"[{finish_count:>3d}/{total_count:03d}] files processed. new finish:",
                        t[0].name,
                        flush=True,
                    )
            time.sleep(0.1)

    # Wait for all threads to complete
    while len(threads) > 0:
        for t in threads:
            if not t[1].is_alive():
                threads.remove(t)
                finish_count += 1
                print(
                    f"[{finish_count:>3d}/{total_count:03d}] files processed. new finish:",
                    t[0].name,
                    flush=True,
                )
        time.sleep(0.1)


if __name__ == "__main__":
    batch()
