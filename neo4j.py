#Axel Cazorla
#3/14/2025
#File to Upload Data onto Neo4j Database

from py2neo import Graph, Node, Relationship

# Connect to Neo4j
graph = Graph("bolt://localhost:7687", auth=("neo4j", "password"))
print("Connected to Neo4j")

# Load nodes from nodes.tsv
#with open("nodes.tsv", "r") as file:
#    lines = file.readlines()[1:]  # Skip header
#    for line in lines:
#        node_id, name, kind = line.strip().split("\t")
#        node = Node(kind, id=node_id, name=name)
#        graph.create(node)
#        print(f"Created node: {node_id}")

# Load relationships from edges.tsv
with open("edges.tsv", "r") as file:
    lines = file.readlines()[1:]  # Skip header
    for line in lines:
        source, metaedge, target = line.strip().split("\t")
        source_node = graph.nodes.match(id=source).first()
        target_node = graph.nodes.match(id=target).first()
        if source_node and target_node:
            rel = Relationship(source_node, metaedge, target_node)
            graph.create(rel)
            print(f"Created relationship: {source} -> {target}")

print("Data loaded successfully")