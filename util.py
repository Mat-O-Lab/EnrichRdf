
import requests
from rdflib import RDF, Graph, Namespace
from rdflib.plugins.sparql import prepareQuery
from rdflib.util import guess_format


RR = Namespace("http://www.w3.org/ns/r2rml#")
RML = Namespace("http://semweb.mmlab.be/ns/rml#")
RDFS = Namespace("http://www.w3.org/2000/01/rdf-schema#")
FNML = Namespace("http://semweb.mmlab.be/ns/fnml#")


#FILTER ( !(?p=rdf:type && isBlank(?o)))
filterBlankTypesAndClasses = prepareQuery(
    """
    SELECT ?s ?p ?o WHERE 
    {
        ?s ?p ?o. FILTER ( !isBlank(?o))
    }
    """
)

deleteClassesAndProperties = prepareQuery(
    """
    SELECT ?s ?p ?o WHERE 
    {
        ?s rdf:type ?t ;
            ?p ?o. 
        FILTER ( ?t=owl:Class 
            || ?t=owl:ObjectProperty
            || ?t=owl:AnnotationProperty
            || ?t=owl:owl:Ontology
            || ?t=rdfs:Class 
            || ?t=rdfs:Datatype
            || ?t=rdf:Property
            ||(?p=rdfs:isDefinedBy && ?o=rdf:))
    }
    """,
    initNs = { "rdf": RDF, "rdfs": RDFS}
)


def getUsedNamespaces(g: Graph):
    """Remove unused prefix in the graph and remove it from the graph"""
    usedNamespaces = []  # List of namespace
    for (
        namespace
    ) in (
        g.namespaces()
    ):  # Iterate for all the namespace in the document check if the namespace is present
        queryCheck = (
            """
            PREFIX """
            + namespace[0]
            + """: <"""
            + str(namespace[1])
            + """>
            select ?x where {
                {
                    ?x ?z ?v.
                    filter(strstarts(str(?x), str("""
            + namespace[0]
            + """:)))
                }
                union
                {
                    ?z ?x ?v.
                    filter(strstarts(str(?x), str("""
            + namespace[0]
            + """:)))
                }
                union
                {
                    ?v ?z ?x.
                    filter(strstarts(str(?x), str("""
            + namespace[0]
            + """:)))
                }

            }"""
        )  # Query to find the places where namespaces are used
        if len(g.query(queryCheck)) >= 1:  # If the namespace is not used anywhere
            usedNamespaces += [namespace]
    return usedNamespaces

def import_ontologies_from_prefixes(g: Graph()) -> (Graph, list):
    namespaces = getUsedNamespaces(g)
    loaded=list()
    succeded=False
    for prefix, namespace in namespaces:
        if prefix=='owl' or str(namespace) == "http://www.w3.org/2002/07/owl":
            continue
        elif str(namespace) == "http://purl.obolibrary.org/obo/":
            source="https://raw.githubusercontent.com/BFO-ontology/BFO-2020/master/21838-2/owl/bfo-2020.owl"
            g.parse(source,format="xml")
            succeded=True
        elif str(namespace) == "https://purl.matolab.org/mseo/mid/":
            source="https://github.com/Mat-O-Lab/MSEO/raw/main/MSEO_mid.ttl"
            g.parse(source,format="turtle")
            succeded=True
        else:
            req = requests.get(namespace, allow_redirects=True)
            # print(req.headers['Content-Type'])
            source=req.url
            return_type = req.headers["Content-Type"].split(";")[0].rsplit("/")[-1]
            if req.status_code == 200 or not return_type=='html':
                if "xml" in return_type:
                    return_type = "xml"
                elif "plain" in return_type:
                    return_type = "turtle"
                fname = req.url.rstrip("/").rsplit("/", 1)[-1]
                if "." not in fname:
                    format = return_type
                else:
                    format = guess_format(fname)
            try:
                g.parse(data=req.text, format=format)
                succeded=True
            except:
                pass
        loaded.append((str(prefix),str(namespace),str(source),str(succeded)))
    return g, loaded