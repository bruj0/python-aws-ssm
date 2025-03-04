import click
import logging
import botocore
import yaml
from python_aws_ssm.parameters import ParameterStore
from json import dumps, loads
from sys import exit
from pathlib import Path


log = logging.getLogger()
log.setLevel(logging.INFO)
parameter_store = ParameterStore()


@click.group()
@click.option("--debug", prompt=False, is_flag=True)
def cli(debug):
    if debug:
        log.setLevel(logging.DEBUG)
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        log.addHandler(handler)

        log.debug("debug logging on")
    pass


@cli.command(no_args_is_help=True)
@click.option("--key", required=True, help="Key to get from SSM")
def get(key: str) -> None:
    """
    Retrieves the value of a key from SSM
    Returns the raw value
    """
    parameters = parameter_store.get_parameters(ssm_key_names=[key])
    print(parameters[key])


@cli.command(no_args_is_help=True)
@click.option("--path", required=True, help="Path to traverse to get all values from")
def tree(path: str) -> None:
    """
    Retrieves all the keys and values under certain path
    
    Returns a json object in the format of {"keyN"="value"}
    """
    parameters = parameter_store.get_parameters_by_path(
        ssm_base_path=path, recursive=True, nested=False
    )
    tmp = {}
    for k, v in parameters.items():
        tmp[k] = loads(v)
    print(dumps(tmp, indent=4))


@cli.command(no_args_is_help=True)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    prompt=False,
    help="Defaults to --no-overwrite",
)
@click.option(
    "--value", default=None, help="A string to be stored in SSM, limit of 4kb"
)
@click.option("--path", help="The name of the key where it will be stored")
@click.argument("file", type=click.Path(exists=True), required=False)
@click.option(
    "--to-json",
    is_flag=True,
    default=False,
    prompt=False,
    help="Enables converting a YAML file to JSON, limit of 4kb",
)
@click.option(
    "--yaml-node", default=None, help="The name of a top level node that will be stored"
)
def put(
    value: str,
    path: str,
    to_json: bool,
    yaml_node: str = None,
    overwrite: bool = False,
    file: str | None = None,
) -> str:
    """
    Stores a string value in a SSM path

    Supports reading from a yaml file , convert it to json and store the result.
    if a yaml node is specified then the content of that node will be stored
    """

    if not file and not value:
        logging.fatal("Either a value or a file must be specified, exiting")
        exit(-2)

    final_value = value
    if file:
        logging.debug(f"Reading from file: {file}")
        final_value = Path(file).read_text()
        # Convert YAML to dictionary and store a node
        if yaml_node:
            try:
                dict_value = yaml.load(final_value, Loader=yaml.FullLoader)
                final_value = dict_value[yaml_node]
            except KeyError:
                logging.fatal(f"Yaml node {yaml_node} not found, exiting")
                exit(-1)
        if to_json:
            final_value = dumps(final_value)

    try:
        ret = parameter_store.put_parameter(
            path=path, value=final_value, overwrite=overwrite
        )
        print(f"{ret}")
    except botocore.exceptions.ClientError as e:
        if e.response["Error"]["Code"] == "ParameterAlreadyExists":
            logging.fatal("The path used already exists as key in SSM, exiting")
        else:
            logging.fatal(f"Error returned: {e}")
        exit(-3)


cli.add_command(get)
cli.add_command(put)
cli.add_command(tree)
if __name__ == "__main__":
    cli()
