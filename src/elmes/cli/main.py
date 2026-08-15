import os
import sys
from pathlib import Path

import click
from langchain.globals import set_debug

SRC_DIR = Path(__file__).resolve().parents[2]
src_dir_str = str(SRC_DIR)

pythonpath_entries = os.environ.get("PYTHONPATH", "").split(os.pathsep)
if src_dir_str not in pythonpath_entries:
    filtered_entries = [entry for entry in pythonpath_entries if entry]
    filtered_entries.append(src_dir_str)
    os.environ["PYTHONPATH"] = os.pathsep.join(filtered_entries)

if src_dir_str not in sys.path:
    sys.path.insert(0, src_dir_str)
from elmes.cli.generate import generate, generate_logic
from elmes.cli.eval import eval, eval_logic
from elmes.cli.visualize import visualize
from elmes.cli.draw import draw
from elmes.cli.export import export
from elmes.cli.export.json_ import export_json_logic
from elmes.debug import maybe_set_local_trace

# default the command arg to be:
# pipeline --config example/knowledge.yaml


@click.command(
    help="Run the pipeline to generate, export JSON files, and evaluate the results."
)
@click.option(
    "--config",
    type=str,
    default="example/knowledge.yaml",
    show_default=True,
    help="Path to the configuration file",
)
@click.option("--debug", is_flag=True, help="Enable debug mode")
def pipeline(config, debug=False):
    set_debug(debug)
    from elmes.config import load_conf

    load_conf(config)
    generate_logic()
    export_json_logic()
    eval_logic(avg=True)


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx):
    if ctx.invoked_subcommand is None:
        ctx.invoke(pipeline)

main.add_command(generate)
main.add_command(export)
main.add_command(eval)
main.add_command(pipeline)
main.add_command(visualize)

main.add_command(draw)
if __name__ == '__main__':
    main()
