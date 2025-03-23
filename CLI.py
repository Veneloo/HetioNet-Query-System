#Axel Cazorla
#3/14/2025
#Script with queries and GUI Implementation with Neo4j and MongoDB integration

from dotenv import load_dotenv
import os
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, filedialog
from py2neo import Graph
from datetime import datetime
from pymongo import MongoClient
import csv
from collections import defaultdict

# Load environment variables
load_dotenv()

# Neo4j credentials
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# MongoDB credentials
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION")
MONGO_DBH = os.getenv("MONGO_DBH")
MONGO_DBN = os.getenv("MONGO_DBN")
MONGO_DBE = os.getenv("MONGO_DBE")

# Additional MongoDB collections for HetioNet data
client = MongoClient(MONGO_URI)
db_hetionet = client[MONGO_DBH]
nodes_col = db_hetionet[MONGO_DBN]
edges_col = db_hetionet[MONGO_DBE]


# Neo4j connection
graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# MongoDB connection
mongo_db = client[MONGO_DB]
log_collection = mongo_db[MONGO_COLLECTION]

# Logging
def log_query(query_type, result):
    log_collection.insert_one({
        "query_type": query_type,
        "result": result,
        "timestamp": datetime.now()
    })

# Fetch diseases
def fetch_disease_ids_neo4j():
    query = "MATCH (d:Disease) RETURN d.id AS DiseaseID"
    result = graph.run(query).data()
    return [d["DiseaseID"] for d in result]

def fetch_disease_ids_mongo():
    return [d["_id"] for d in nodes_col.find({"kind": "Disease"}, {"_id": 1})]

def format_list(items, label, widget):
    widget.insert(tk.END, f"{label}:\n", "bold")
    if not items:
        widget.insert(tk.END, "   - None\n")
    for item in items:
        widget.insert(tk.END, f"   - {item}\n")

# Unified query handlers
def query_disease_info():
    if db_mode.get() == "mongodb":
        query_disease_info_mongo()
    else:
        query_disease_info_neo4j()

def query_new_treatments():
    if db_mode.get() == "mongodb":
        query_new_treatments_mongo()
    else:
        query_new_treatments_neo4j()

# Neo4j Queries 
def query_disease_info_neo4j():
    disease_id = disease_var.get().strip()
    if not disease_id:
        messagebox.showwarning("Input Error", "Please enter a Disease ID.")
        return
    query = """
    MATCH (d:Disease {id: $disease_id})
    OPTIONAL MATCH (c:Compound)-[:CtD|:CpD]->(d)
    OPTIONAL MATCH (g:Gene)<-[:DdG|:DuG|:DaG]-(d)
    OPTIONAL MATCH (a:Anatomy)<-[:DlA]-(d)
    RETURN d.name AS DiseaseName,
           collect(DISTINCT c.name) AS DrugNames,
           collect(DISTINCT g.name) AS GeneNames,
           collect(DISTINCT a.name) AS AnatomyNames;
    """
    result = graph.run(query, disease_id=disease_id).data()
    output_text.delete("1.0", tk.END)
    if result and result[0]['DiseaseName']:
        info = result[0]
        output_text.insert(tk.END, "🦠 Disease Name: ", "bold")
        output_text.insert(tk.END, f"{info['DiseaseName']}\n\n")
        format_list(info['DrugNames'], "🔹 Drugs", output_text)
        format_list(info['GeneNames'], "🔹 Genes", output_text)
        format_list(info['AnatomyNames'], "🔹 Anatomy Locations", output_text)
        log_query("disease_info", info)
    else:
        messagebox.showinfo("No Results", "No disease found with the given ID.")

def query_new_treatments_neo4j():
    query = """
    MATCH (c:Compound)
    WHERE NOT EXISTS { (c)-[:CtD|CpD]->(:Disease) }
    MATCH (c)-[:CuG|CdG]->(g:Gene)
    MATCH (a:Anatomy)-[:AuG|AdG]->(g)
    MATCH (d:Disease)-[:DuG|DdG]->(g)
    WHERE 
        ( (c)-[:CuG]->(g) AND (a)-[:AdG]->(g) )
        OR
        ( (c)-[:CdG]->(g) AND (a)-[:AuG]->(g) )
    RETURN DISTINCT c.id AS CompoundID, c.name AS CompoundName
    ORDER BY c.name;
    """
    result = graph.run(query).data()
    output_text.delete("1.0", tk.END)
    if result:
        output_text.insert(tk.END, "🧪 Potential New Treatments:\n", "bold")
        output_text.insert(tk.END, "-" * 50 + "\n")
        for c in result:
            output_text.insert(tk.END, f"💊 {c['CompoundName']} ({c['CompoundID']})\n")
        log_query("new_treatments", result)
    else:
        messagebox.showinfo("No Results", "No treatments found.")

# MongoDB Queries
def query_disease_info_mongo():
    disease_id = disease_var.get().strip()
    disease = nodes_col.find_one({"_id": disease_id})
    if not disease:
        messagebox.showinfo("No Results", "No disease found with the given ID.")
        return
    drug_ids = [e["source"] for e in edges_col.find({"target": disease_id, "metaedge": {"$in": ["CtD", "CpD"]}})]
    gene_ids = [e["target"] for e in edges_col.find({"source": disease_id, "metaedge": {"$in": ["DdG", "DuG", "DaG"]}})]
    anatomy_ids = [e["target"] for e in edges_col.find({"source": disease_id, "metaedge": "DlA"})]

    drugs = [n["name"] for n in nodes_col.find({"_id": {"$in": drug_ids}})]
    genes = [n["name"] for n in nodes_col.find({"_id": {"$in": gene_ids}})]
    anatomies = [n["name"] for n in nodes_col.find({"_id": {"$in": anatomy_ids}})]

    output_text.delete("1.0", tk.END)
    output_text.insert(tk.END, "🦠 Disease Name: ", "bold")
    output_text.insert(tk.END, f"{disease['name']}\n\n")
    format_list(drugs, "🔹 Drugs", output_text)
    format_list(genes, "🔹 Genes", output_text)
    format_list(anatomies, "🔹 Anatomy Locations", output_text)
    log_query("disease_info", {"disease": disease["name"], "drugs": drugs, "genes": genes, "anatomies": anatomies})


def query_new_treatments_mongo():
    """Optimized MongoDB version of new treatment query."""
    output_text.delete("1.0", tk.END)

    # Step 1: Load all relevant edges (CuG, CdG, AuG, AdG, DuG, DdG)
    regulatory_edges = list(edges_col.find({
        "metaedge": {"$in": ["CuG", "CdG", "AuG", "AdG", "DuG", "DdG"]}
    }))

    # Step 2: Map compounds to regulated genes, genes to anatomy/disease
    compound_to_genes = defaultdict(list)
    gene_to_anatomy = defaultdict(set)
    gene_to_disease = defaultdict(set)

    for edge in regulatory_edges:
        metaedge = edge["metaedge"]
        source = edge["source"]
        target = edge["target"]

        if metaedge in ["CuG", "CdG"]:
            compound_to_genes[source].append((target, metaedge))
        elif metaedge in ["AuG", "AdG"]:
            gene_to_anatomy[target].add(metaedge)
        elif metaedge in ["DuG", "DdG"]:
            gene_to_disease[target].add(metaedge)

    # Step 3: Get already-used treatments
    treated_compounds = set(
        edge["source"]
        for edge in edges_col.find({"metaedge": {"$in": ["CtD", "CpD"]}}, {"source": 1})
    )

    # Step 4: Apply treatment logic
    candidate_ids = set()
    for compound, gene_list in compound_to_genes.items():
        if compound in treated_compounds:
            continue

        for gene, effect in gene_list:
            anat_directions = gene_to_anatomy.get(gene)
            dis_directions = gene_to_disease.get(gene)

            if not anat_directions or not dis_directions:
                continue

            if ((effect == "CuG" and "AdG" in anat_directions) or
                (effect == "CdG" and "AuG" in anat_directions)):
                candidate_ids.add(compound)
                break

    result = list(
        nodes_col.find(
            {"_id": {"$in": list(candidate_ids)}},
            {"_id": 1, "name": 1}
        ).sort("name", 1)  # Sort ascending (alphabetically)
    )

    if result:
        output_text.insert(tk.END, "🧪 Potential New Treatments:\n", "bold")
        output_text.insert(tk.END, "-" * 50 + "\n")
        for c in result:
            output_text.insert(tk.END, f"💊 {c['name']} ({c['_id']})\n")
        log_query("new_treatments", result)
    else:
        messagebox.showinfo("No Results", "No new treatments found.")


# Save logs
def save_logs():
    last_log = log_collection.find_one(sort=[("_id", -1)])
    if not last_log:
        messagebox.showinfo("No Logs", "No logs to save.")
        return
    path = filedialog.asksaveasfilename(defaultextension=".txt")
    if not path:
        return
    with open(path, "w", encoding="utf-8") as file:
        file.write(f"🔹 Query Type: {last_log.get('query_type')}\n")
        file.write(f"📅 Timestamp: {last_log.get('timestamp')}\n")
        file.write("🔍 Result:\n")
        file.write(str(last_log.get("result", "")) + "\n")

# Dropdown filtering
def update_dropdown(*args):
    term = disease_var.get().lower()
    filtered = [d for d in disease_ids if term in d.lower()]
    disease_dropdown["values"] = filtered

def refresh_disease_ids(event=None):
    global disease_ids
    disease_ids = fetch_disease_ids_mongo() if db_mode.get() == "mongodb" else fetch_disease_ids_neo4j()
    disease_dropdown["values"] = disease_ids

# ===================== GUI =====================
root = tk.Tk()
root.title("HetioNet Query System")
root.geometry("700x650")
root.configure(bg="#f4f4f4")

style = ttk.Style()
style.configure("TButton", font=("Arial", 12), padding=6)
style.configure("TLabel", font=("Arial", 12))
style.configure("TEntry", font=("Arial", 12))
style.configure("TCombobox", font=("Arial", 12))

disease_frame = tk.Frame(root, bg="#f4f4f4")
disease_frame.pack(pady=10)

tk.Label(disease_frame, text="Enter Disease ID:", bg="#f4f4f4", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
disease_var = tk.StringVar()
disease_var.trace_add("write", update_dropdown)
disease_dropdown = ttk.Combobox(disease_frame, textvariable=disease_var, width=50)
disease_dropdown.pack(side=tk.LEFT, padx=5)

query_disease_btn = ttk.Button(disease_frame, text="Query Disease", command=query_disease_info)
query_disease_btn.pack(side=tk.LEFT, padx=5)

# Database toggle
db_mode = tk.StringVar(value="neo4j")
db_frame = tk.Frame(root, bg="#f4f4f4")
db_frame.pack(pady=5)
tk.Label(db_frame, text="Select Database:", bg="#f4f4f4", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
db_selector = ttk.Combobox(db_frame, textvariable=db_mode, values=["neo4j", "mongodb"], state="readonly", width=10)
db_selector.pack(side=tk.LEFT, padx=5)
db_selector.bind("<<ComboboxSelected>>", refresh_disease_ids)

# Buttons
ttk.Button(root, text="Find Potential New Treatments", command=query_new_treatments).pack(pady=5)
ttk.Button(root, text="Save Logs", command=save_logs).pack(pady=5)

# Output
output_text = scrolledtext.ScrolledText(root, width=80, height=25, wrap=tk.WORD, font=("Courier", 10))
output_text.pack(pady=10)
output_text.tag_configure("bold", font=("Courier", 10, "bold"))

# Initialize dropdown
disease_ids = fetch_disease_ids_neo4j()
disease_dropdown["values"] = disease_ids

# Launch
root.mainloop()
