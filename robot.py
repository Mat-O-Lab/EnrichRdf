# hermit.py
import os, sys
import subprocess
from fastapi import HTTPException
from rdflib import Graph
import logging
import uuid
import json

_HERE = os.path.dirname(__file__)
_HERMIT_CLASSPATH = os.pathsep.join([os.path.join(_HERE, "hermit"), os.path.join("hermit", "HermiT.jar")])
JAVA_MEMORY=1024
_HERMIT_JAR=os.path.join("/","hermit", "HermiT.jar")
print(_HERMIT_JAR)

from enum import Enum

class Reasoner(str, Enum):
    ELK="ELK"
    hermiT="hermit"
    JFact="jfact"
    Whelk="whelk"
    ExpressionMaterializingReasoner="emr"
    StructuralReasoner="structural"


def reason(g=Graph(), reasoner: Reasoner=Reasoner.ELK, debug=True)-> Graph:
    #axiom_generators="SubClass EquivalentClass DisjointClasses EquivalentClass ClassAssertion PropertyAssertion EquivalentObjectProperty InverseObjectProperties ObjectPropertyCharacteristic SubObjectProperty"
    #axiom_generators="SubClass DisjointClasses EquivalentClass ClassAssertion PropertyAssertion EquivalentObjectProperty InverseObjectProperties"
    #axiom_generators="SubClass ClassAssertion SubObjectProperty EquivalentObjectProperty InverseObjectProperties"
    axiom_generators="SubClass EquivalentClass ClassAssertion SubObjectProperty EquivalentObjectProperty InverseObjectProperties ObjectPropertyCharacteristic PropertyAssertion"
    len_input=len(g) 
    temp_id=str(uuid.uuid4())
    output_path=os.path.join(_HERE, temp_id+'.ttl')
    input_path=os.path.join(_HERE, temp_id+'.owl')
    #convert_path=os.path.join(_HERE, 'output.ttl')
    g.serialize(input_path,format='application/rdf+xml')
    command = ["robot", "reason", "--reasoner", reasoner, "-vvv", "--axiom-generators", axiom_generators,"-i", input_path, "-o", output_path]
    logging.debug("* Running Robot Reason...")
    logging.debug(command)
    try:
        output = subprocess.check_output(command, stderr = subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(e.output)
        os.remove(input_path)
        raise HTTPException(status_code=400, detail="Java error message is: {}".format(e.stderr or e.output or b""))
    else:
        g.parse(output_path)
        os.remove(output_path)
        os.remove(input_path)
    len_output=len(g)
    logging.info('Infered {} tripples'.format(len_output-len_input))
    return g

import requests, tempfile

class RobotExeption(Exception):
    pass

def run_robot_convert(file_path,outname,format):
    command = ["robot", "convert", "-i", file_path, "-o", outname, "--format", format]
    logging.debug("* Running Robot Connvert...")
    try:
        output = subprocess.check_output(command, stderr = subprocess.STDOUT)
        with open(outname, 'rb') as file:
            raw_bytes = file.read()
        os.remove(outname)
    except subprocess.CalledProcessError as e:
            raise RobotExeption("Java error message is: {}".format(e.stderr or e.output.decode() or b""))
        
    return raw_bytes

from pathlib import Path
def convert(file_loc: str, outname, format='ttl')-> bytes:
    file_path=Path(file_loc)
    if file_path.exists():
        print("got file location")
        file_path=file_path.as_posix()
    else:
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            response = requests.get(file_loc)
            if response.status_code == 200:
                temp_file.write(response.content)
                file_path = temp_file.name
                print(f"File downloaded to: {file_path}")
            else:
                print("Failed to download file:", response.status_code)
                return None
            #outname=file_loc.rsplit('/',1)[-1].rsplit('.',1)[0]+'.'+format
    print(file_path)
    logging.debug("* Running Robot Connvert...")
    raw_bytes=run_robot_convert(file_path,outname,format)
    return raw_bytes, outname

def analyse(g=Graph(), format: str="json") -> str:
    temp_id=str(uuid.uuid4())
    output_path=os.path.join(_HERE, temp_id+'.'+format)
    input_path=os.path.join(_HERE, temp_id+'.owl')
    #convert_path=os.path.join(_HERE, 'output.ttl')
    g.serialize(input_path,format='application/rdf+xml')
    command = ["robot", "report", "-i", input_path, "-o", output_path]
    logging.debug("* Running Robot Report...")
    try:
        output = subprocess.check_output(command, stderr = subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        if os.path.isfile(output_path):
            pass
        else:
            os.remove(input_path)
            raise HTTPException(status_code=400, detail="Java error message is: {}".format(e.stderr or e.output or b""))
    os.remove(input_path)
    with open(output_path,"rb") as f:
        res=json.load(f)
    os.remove(output_path)
    return res

    