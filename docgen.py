#!/usr/bin/python3

import sys
import subprocess

if (len(sys.argv) != 2):
    print(f"Usage: {sys.argv[0]} <markdown file>")
    sys.exit(-1)

def run_command(c):
    try:
        result = subprocess.run(c, shell = True, check = True, capture_output = True, text = True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error: shell command, {c}, in eval block failed: {e}")
    except Exception as e:
        print(f"Error: executing shell command {c} resulted in in unknown exception {e}")

def process(f):
    output = ""
    in_eval_blk = False
    cmd = ""
    for l in f:
        if in_eval_blk and l.strip() == "```":
            output += l
            output += f"Autogenerated with command: `{cmd.strip()}`.\n"
            cmd = ""
            in_eval_blk = False
        elif in_eval_blk:
            cmd += l
            output += run_command(l)
        elif not in_eval_blk and (l.strip() == "``` eval" or l.strip() == "```eval"):
            in_eval_blk = True
            output += "```sh\n"
        else:
            output += l
    return output

try:
    with open(sys.argv[1], 'r') as f:
        out = process(f)
        print(out)
except FileNotFoundError:
    print(f"Error: could not open document file {sys.argv[1]}")
except Exception as e:
    print(f"Error: opening document file {sys.argv[1]} resulted in unknown exception {e}")
