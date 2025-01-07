import matplotlib.pyplot as plt
import pandas as pd
from bs4 import BeautifulSoup

with open("../Report Generator/database_usage_report.html", "r", encoding="utf-8") as file:
    soup = BeautifulSoup(file, "html.parser")

h4s = soup.find_all("h4")
data = []

for h4s in h4s:
    if h4s.get_text().strip() != "Reference Summary":
        continue

    ref_summary = h4s.find_next("table")
    if not ref_summary:
        continue
        
    h3 = h4s.find_previous("h3")
    table_name = h3.get_text().strip()

    rows = ref_summary.find_all("tr")[1:]  # Ignorer l'en-tête
    summary = {row.find_all("td")[0].get_text(): int(row.find_all("td")[1].get_text()) for row in rows}
    summary["name"] = table_name
    data.append(summary)

df = pd.DataFrame(data).fillna(0)

stack_columns = [col for col in df.columns if col != "name"]

df.set_index("name")[stack_columns].plot(kind="bar", stacked=True, figsize=(15, 8))
plt.title("Graphique empilé du type de requête par table")
plt.xlabel("Tables")
plt.ylabel("Nombre de requêtes")
plt.legend(title="Légende", bbox_to_anchor=(1.05, 1), loc='upper left')
plt.tight_layout()

# Sauvegarder ou afficher
plt.savefig("stats.png")
plt.show()
