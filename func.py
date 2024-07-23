from parliament import Context

from neomodel import config
from neo4j import GraphDatabase

from neomodel import (config, StructuredNode, StringProperty, IntegerProperty,
	UniqueIdProperty, RelationshipTo, RelationshipFrom, Relationship, One, OneOrMore,
    DateTimeProperty)
from neomodel.properties import JSONProperty
from neomodel import db

from cloudevents.http import from_http
import sys
import os
import re

from flask import Request

neo4j_url = os.getenv("NEO4J_URL")
neo4j_username = os.getenv("NEO4J_USERNAME")
neo4j_password = os.getenv("NEO4J_PASSWORD")


config.DATABASE_URL = f"bolt://{neo4j_username}:{neo4j_password}@{neo4j_url}"
config.DRIVER = GraphDatabase.driver(f"bolt://{neo4j_url}")

class MindwmUser(StructuredNode):
    username = StringProperty(required = True)
    host = RelationshipTo('MindwmHost', 'HAS_MINDWM_HOST')

class MindwmHost(StructuredNode):
    hostname = StringProperty(required = True)
    tmux = RelationshipTo('Tmux', 'HAS_TMUX', cardinality=OneOrMore)

class Tmux(StructuredNode):
    socket_path = StringProperty(required = True)
    host_id = IntegerProperty(required = True)
    host = RelationshipFrom('MindwmHost', 'HAS_TMUX', cardinality=One)
    session = RelationshipTo('TmuxSession', 'HAS_TMUX_SESSION', cardinality=OneOrMore)

class TmuxSession(StructuredNode):
    name = StringProperty(required = True)
    tmux_id = IntegerProperty(required = True)
    socket_path = RelationshipFrom('Tmux', 'HAS_TMUX', cardinality=One)
    pane = RelationshipTo('TmuxPane', 'HAS_TMUX_PANE', cardinality=OneOrMore)

class TmuxPane(StructuredNode):
    pane_id = IntegerProperty(required = True)
    session_id = IntegerProperty(required = True)
    session = RelationshipFrom('TmuxSession', 'HAS_TMUX_PANE', cardinality=One)
    title = StringProperty()
    contextParameters = JSONProperty(default={})
    io_document = Relationship('IoDocument', 'HAS_IO_DOCUMENT')

class IoDocument(StructuredNode):
    uuid = StringProperty(unique_index=True, required = True)
    user_input = StringProperty(required = True)
    output = StringProperty(required = True)
    ps1 = StringProperty(required = True)
    time = DateTimeProperty(default_now = True)
    tmux_pane = Relationship('TmuxPane', 'HAS_IO_DOCUMENT')

def  main(context: Context):
    """ 
    Function template
    The context parameter contains the Flask request object and any
    CloudEvent received with the request.
    """

    # Add your business logic here
    event = from_http(context.request.headers, context.request.data)

    data = event.data
    payload = data['payload']
    id = payload['id']
    after = payload['after']
    properties = after['properties']
    user_input = properties['user_input']
    mindwm_prefix = os.getenv("MINDWM_PREFIX", "")
    pattern = fr"#\s*{re.escape(mindwm_prefix)}\s+(\w+)\s*=\s*(.*)"
    match = re.match(pattern, user_input)
    if match:
        key = match.group(1)
        value = match.group(2)
        print(f'{key}: {value}', file=sys.stderr)

        results, meta = db.cypher_query(f"MATCH (n:IoDocument) WHERE ID(n) = {id}  RETURN n;")
        iodoc = IoDocument.inflate(results[meta.index('n')][0])
        tmux_pane = iodoc.tmux_pane.get()

        if value != "":
            print('save', file=sys.stderr)
            tmux_pane.contextParameters[key] = value
            tmux_pane.save()
        else:
            print('delete', file=sys.stderr)
            del tmux_pane.contextParameters[key]
            tmux_pane.save()
    elif "# show" in user_input:
        results, meta = db.cypher_query(f"MATCH (n:IoDocument) WHERE ID(n) = {id}  RETURN n;")
        iodoc = IoDocument.inflate(results[meta.index('n')][0])
        tmux_pane = iodoc.tmux_pane.get()
        for key, value in tmux_pane.contextParameters.items():
            print(f"{key} = {value}", file=sys.stderr)
        #print(tmux_pane.contextParameters, file=sys.stderr)

    return "", 200
