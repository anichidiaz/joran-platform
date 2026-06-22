import streamlit as st
import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
 
load_dotenv()
 
JIRA_URL = os.getenv("JIRA_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_TOKEN")
 
st.set_page_config(page_title="Joran Platform", layout="wide")
 
st.sidebar.title("Joran 🤖")
st.sidebar.caption("Unified Operations Platform")
st.sidebar.write("---")
 
opcion = st.sidebar.radio(
    "Select a platform:",
    ["📊 General Dashboard", "📋 JIRA Management", "💽 FinIQ Environment"],
    label_visibility="visible"
)
 
if opcion == "📊 General Dashboard":
    st.title("📊 General Status Dashboard")
    st.write("Welcome to Joran. Select an option from the left menu to operate your platforms.")
 
elif opcion == "📋 JIRA Management":
    st.title("📋 Official JIRA Connector (Live Data)")
 
    tipo_jira = st.radio(
        "Which JIRAs do you want to see?",
        ["All", "Client", "Internal"],
        horizontal=True
    )
 
    estado_placeholder = st.empty()
    estado_placeholder.info("Connecting to finiq.atlassian.net...")
 
    def obtener_todos_los_tickets(tipo_filtro):
        auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
        headers = {"Accept": "application/json"}
 
        if tipo_filtro == "Client":
            jql = "project = 'BBVA_Fixed_Income_Client' ORDER BY updated DESC"
        elif tipo_filtro == "Internal":
            jql = "project = 'BBVA_Fixed_Income_Internal' ORDER BY updated DESC"
        else:
            jql = "project is not EMPTY ORDER BY updated DESC"
 
        todos_los_tickets = []
        start_at = 0
        page_size = 50
 
        while True:
            try:
                response = requests.get(
                    f"{JIRA_URL}/rest/api/3/search/jql",
                    params={
                        "jql": jql,
                        "startAt": start_at,
                        "maxResults": page_size,
                        "fields": "summary,status,issuetype,priority,project,assignee,reporter"
                    },
                    headers=headers,
                    auth=auth,
                    timeout=15
                )
 
                if response.status_code != 200:
                    return [], f"ERROR_HTTP_{response.status_code}"
 
                datos = response.json()
                issues = datos.get("issues", [])
                total = datos.get("total", 0)
 
                for issue in issues:
                    todos_los_tickets.append({
                        "ID": issue["key"],
                        "Project": issue["fields"].get("project", {}).get("name", "—"),
                        "Summary": issue["fields"].get("summary", "No title"),
                        "Type": issue["fields"]["issuetype"]["name"] if issue["fields"].get("issuetype") else "—",
                        "Status": issue["fields"]["status"]["name"] if issue["fields"].get("status") else "—",
                        "Priority": issue["fields"]["priority"]["name"] if issue["fields"].get("priority") else "—",
                        "Assigned to": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "Unassigned",
                        "Reported by": issue["fields"]["reporter"]["displayName"] if issue["fields"].get("reporter") else "—",
                    })
 
                start_at += page_size
 
                if start_at >= total:
                    break
 
            except requests.exceptions.Timeout:
                return [], "ERROR_TIMEOUT"
            except Exception as e:
                return [], "ERROR_GENERIC"
 
        return todos_los_tickets, "REAL"
 
    lista_tickets, origen = obtener_todos_los_tickets(tipo_jira)
 
    if origen == "REAL" and lista_tickets:
        estado_placeholder.success(f"✅ {len(lista_tickets)} tickets synced with Atlassian.")
 
        import pandas as pd
        df = pd.DataFrame(lista_tickets)
 
        st.write("**Select a row to see full details:**")
        seleccion = st.dataframe(
            df,
            use_container_width=True,
            selection_mode="single-row",
            on_select="rerun",
            key="tabla_jira"
        )
 
        filas_seleccionadas = seleccion.selection.rows
        if filas_seleccionadas:
            indice = filas_seleccionadas[0]
            ticket_id = lista_tickets[indice]["ID"]
 
            st.divider()
            st.subheader(f"📄 Full details: {ticket_id}")
 
            with st.spinner(f"Loading details for {ticket_id}..."):
                url_detalle = f"{JIRA_URL}/rest/api/3/issue/{ticket_id}?expand=renderedFields,changelog,attachment,comment"
                auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
                headers = {"Accept": "application/json"}
 
                try:
                    r = requests.get(url_detalle, headers=headers, auth=auth, timeout=10)
                    if r.status_code == 200:
                        issue = r.json()
                        fields = issue.get("fields", {})
 
                        col1, col2, col3 = st.columns(3)
                        col1.metric("Status", fields.get("status", {}).get("name", "—"))
                        col2.metric("Type", fields.get("issuetype", {}).get("name", "—"))
                        col3.metric("Priority", fields.get("priority", {}).get("name", "—") if fields.get("priority") else "—")
 
                        st.markdown(f"### {fields.get('summary', 'No title')}")
 
                        col4, col5 = st.columns(2)
                        assignee = fields.get("assignee")
                        reporter = fields.get("reporter")
                        col4.write(f"👤 **Assigned to:** {assignee['displayName'] if assignee else 'Unassigned'}")
                        col5.write(f"📝 **Reported by:** {reporter['displayName'] if reporter else '—'}")
 
                        col6, col7 = st.columns(2)
                        col6.write(f"📅 **Created:** {fields.get('created', '—')[:10] if fields.get('created') else '—'}")
                        col7.write(f"🔄 **Updated:** {fields.get('updated', '—')[:10] if fields.get('updated') else '—'}")
 
                        st.write("---")
                        st.write("**📋 Description:**")
                        descripcion = fields.get("description")
                        if descripcion and descripcion.get("content"):
                            texto = []
                            for bloque in descripcion["content"]:
                                for item in bloque.get("content", []):
                                    if item.get("type") == "text":
                                        texto.append(item.get("text", ""))
                            st.write(" ".join(texto) if texto else "_No description_")
                        else:
                            st.write("_No description_")
 
                        adjuntos = fields.get("attachment", [])
                        if adjuntos:
                            st.write("---")
                            st.write(f"**📎 Attachments ({len(adjuntos)}):**")
                            for adj in adjuntos:
                                nombre = adj.get("filename", "file")
                                url_adj = adj.get("content", "")
                                mime = adj.get("mimeType", "")
                                if mime.startswith("image/"):
                                    try:
                                        img_response = requests.get(url_adj, auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN), timeout=10)
                                        if img_response.status_code == 200:
                                            st.image(img_response.content, caption=nombre, use_container_width=True)
                                    except:
                                        st.write(f"🖼️ Could not load image: {nombre}")
                                else:
                                    st.markdown(f"📄 [{nombre}]({url_adj})")
 
                        comentarios = fields.get("comment", {}).get("comments", [])
                        if comentarios:
                            st.write("---")
                            st.write(f"**💬 Comments ({len(comentarios)}):**")
                            for com in comentarios:
                                autor = com.get("author", {}).get("displayName", "Unknown")
                                fecha = com.get("created", "")[:10]
                                cuerpo = com.get("body", {})
                                texto_com = []
                                if isinstance(cuerpo, dict):
                                    for bloque in cuerpo.get("content", []):
                                        for item in bloque.get("content", []):
                                            if item.get("type") == "text":
                                                texto_com.append(item.get("text", ""))
                                texto_final = " ".join(texto_com) if texto_com else "_No text_"
                                with st.expander(f"💬 {autor} — {fecha}"):
                                    st.write(texto_final)
 
                        changelog = issue.get("changelog", {}).get("histories", [])
                        if changelog:
                            st.write("---")
                            st.write(f"**🕓 Change history ({len(changelog)}):**")
                            with st.expander("View full history"):
                                for cambio in reversed(changelog):
                                    autor = cambio.get("author", {}).get("displayName", "—")
                                    fecha = cambio.get("created", "")[:10]
                                    for item in cambio.get("items", []):
                                        campo = item.get("field", "—")
                                        antes = item.get("fromString", "—")
                                        despues = item.get("toString", "—")
                                        st.write(f"• `{fecha}` **{autor}** changed **{campo}**: _{antes}_ → _{despues}_")
 
                        st.write("---")
                        st.markdown(f"🔗 [Open in Jira]({JIRA_URL}/browse/{ticket_id})")
 
                    else:
                        st.error(f"Error loading details: HTTP {r.status_code}")
 
                except Exception as e:
                    st.error(f"Connection error: {e}")
 
    elif origen == "REAL" and not lista_tickets:
        estado_placeholder.warning("Connection OK but no tickets visible for your user.")
    else:
        estado_placeholder.warning(f"Could not connect ({origen}).")
 
elif opcion == "💽 FinIQ Environment":
    st.title("💽 Euroconnect Equity Structures")
    st.write("Test environment configuration:")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("On behalf Of", value="DESHAW")
        st.selectbox("Format", ["Note", "Certificate"])
    with col2:
        st.selectbox("Coupon Type", ["Conditional with memory", "Fixed"])
        st.checkbox("Memory Coupon", value=True)
 