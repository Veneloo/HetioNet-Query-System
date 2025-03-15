#CLI Script
from dotenv import load_dotenv
import os
import tkinter as tk
from tkinter import scrolledtext, messagebox, ttk, filedialog
from py2neo import Graph
from datetime import datetime
from pymongo import MongoClient
import csv

#Load enviroment variables from .env   
load_dotenv()

#Getting Credentials
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION")

# Connect to Neo4j
graph = Graph(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# Connect to MongoDB (for logging)
client = MongoClient(MONGO_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]

def log_query(query_type, result):
    """Log queries to MongoDB."""
    log_entry = {
        "query_type": query_type,
        "result": result,
        "timestamp": datetime.now()
    }
    collection.insert_one(log_entry)

def fetch_disease_ids():
    """Fetch all disease IDs from the database for dropdown suggestions."""
    query = "MATCH (d:Disease) RETURN d.id AS DiseaseID"
    result = graph.run(query).data()
    return [d["DiseaseID"] for d in result]

def format_list(items, label, text_widget):
    """Formats lists into a clean multi-line output with bold headers."""
    if not items:
        text_widget.insert(tk.END, f"{label}: None\n", "bold")
        return
    
    text_widget.insert(tk.END, f"{label}:\n", "bold")
    for item in items:
        text_widget.insert(tk.END, f"   - {item}\n")

def query_disease_info():
    """Query disease information by ID from Tkinter input."""
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
        
        # Disease Name (Bold)
        output_text.insert(tk.END, "🦠 Disease Name: ", "bold")
        output_text.insert(tk.END, f"{info['DiseaseName']}\n\n")

        # Drugs, Genes, and Anatomy with formatted list output
        format_list(info['DrugNames'], "🔹 Drugs", output_text)
        format_list(info['GeneNames'], "🔹 Genes", output_text)
        format_list(info['AnatomyNames'], "🔹 Anatomy Locations", output_text)

        log_query("disease_info", info)
    else:
        messagebox.showinfo("No Results", "No disease found with the given ID.")

def query_new_treatments():
    """Find new potential treatments while ensuring no duplicates from existing drugs."""
    
    query = """
    MATCH (c:Compound)
    WHERE NOT EXISTS { (c)-[:CtD|CpD]->(:Disease) }  // Exclude existing treatments

    MATCH (c)-[:CuG|CdG]->(g:Gene)  // Compound up/down-regulates Gene
    MATCH (a:Anatomy)-[:AuG|AdG]->(g)  // Anatomy up/down-regulates Gene
    MATCH (d:Disease)-[:DuG|DdG]->(g)  // Disease up/down-regulates Gene
    WHERE 
        ( (c)-[:CuG]->(g) AND (a)-[:AdG]->(g) )  // Compound up, Anatomy down
        OR
        ( (c)-[:CdG]->(g) AND (a)-[:AuG]->(g) )  // Compound down, Anatomy up

    RETURN DISTINCT c.id AS CompoundID, c.name AS CompoundName
    ORDER BY c.name;
    """
    result = graph.run(query).data()
    
    output_text.delete("1.0", tk.END)
    if result:
        output_text.insert(tk.END, "🧪 Potential New Treatments:\n", "bold")
        output_text.insert(tk.END, "-" * 50 + "\n")
        for compound in result:
            output_text.insert(tk.END, f"💊 {compound['CompoundName']} ({compound['CompoundID']})\n")
        log_query("new_treatments", result)
    else:
        messagebox.showinfo("No Results", "No potential new treatments found.")

def save_logs():
    """Allow the user to save only the most recent log from MongoDB."""
    last_log = collection.find_one(sort=[("_id", -1)])  # Fetch the latest log

    if not last_log:
        messagebox.showinfo("No Logs", "No logs found to save.")
        return

    # Let the user choose file type and name
    filetypes = [("Text file", "*.txt"), ("CSV file", "*.csv")]
    file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=filetypes)

    if not file_path:
        return  # User canceled the save dialog

    if file_path.endswith(".txt"):
        with open(file_path, "w", encoding="utf-8") as file:
            file.write(f"🔹 Query Type: {last_log.get('query_type', 'Unknown')}\n")
            file.write(f"📅 Timestamp: {last_log.get('timestamp', 'Unknown')}\n")
            file.write("🔍 Result:\n")
            file.write(str(last_log.get('result', 'No result recorded')) + "\n")
            file.write("=" * 60 + "\n\n")
    elif file_path.endswith(".csv"):
        with open(file_path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["Query Type", "Timestamp", "Result"])
            writer.writerow([last_log.get('query_type', 'Unknown'), last_log.get('timestamp', 'Unknown'), last_log.get('result', 'No result recorded')])

    messagebox.showinfo("Success", f"Log saved to {file_path}")


def update_dropdown(*args):
    """Update the dropdown suggestions based on user input."""
    search_term = disease_var.get().lower()
    if search_term:
        filtered_diseases = [d for d in disease_ids if search_term in d.lower()]
        disease_dropdown["values"] = filtered_diseases

# Fetch disease IDs for dropdown
disease_ids = fetch_disease_ids()

# Create main window
root = tk.Tk()
root.title("HetioNet Query System")
root.geometry("700x650")
root.configure(bg="#f4f4f4")

# Styling
style = ttk.Style()
style.configure("TButton", font=("Arial", 12), padding=6)
style.configure("TLabel", font=("Arial", 12))
style.configure("TEntry", font=("Arial", 12))
style.configure("TCombobox", font=("Arial", 12))

# Disease Query UI
disease_frame = tk.Frame(root, bg="#f4f4f4")
disease_frame.pack(pady=10)

tk.Label(disease_frame, text="Enter Disease ID:", bg="#f4f4f4", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
disease_var = tk.StringVar()
disease_var.trace_add("write", update_dropdown)
disease_dropdown = ttk.Combobox(disease_frame, textvariable=disease_var, width=50)
disease_dropdown["values"] = disease_ids
disease_dropdown.pack(side=tk.LEFT, padx=5)
query_disease_btn = ttk.Button(disease_frame, text="Query Disease", command=query_disease_info)
query_disease_btn.pack(side=tk.LEFT, padx=5)

# New Treatments Button
query_treatments_btn = ttk.Button(root, text="Find Potential New Treatments", command=query_new_treatments)
query_treatments_btn.pack(pady=5)

# Save Logs Button
save_logs_btn = ttk.Button(root, text="Save Logs", command=save_logs)
save_logs_btn.pack(pady=5)

# Output Text Area
output_text = scrolledtext.ScrolledText(root, width=80, height=25, wrap=tk.WORD, font=("Courier", 10))
output_text.pack(pady=10)

# Define text formatting (Bold)
output_text.tag_configure("bold", font=("Courier", 10, "bold"))

# Run the GUI
root.mainloop()
