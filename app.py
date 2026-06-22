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

def obtener_tickets_reales_jira():
    url = f"{JIRA_URL}/rest/api/3/search/jql"

    payload = {
        "jql": "project is not EMPTY ORDER BY updated DESC",  # Sin filtro — trae todos los tickets visibles para tu usuario
        "maxResults": 50,
        "fields": ["summary", "status", "issuetype", "priority", "project", "assignee", "reporter"]
    }

    auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, json=payload, headers=headers, auth=auth, timeout=10)
        

        if response.status_code == 200:
            datos = response.json()
            tickets_limpios = []
            for issue in datos.get("issues", []):
                tickets_limpios.append({
                    "ID": issue["key"],
                    "Proyecto": issue["fields"].get("project", {}).get("name", "—"),
                    "Resumen": issue["fields"].get("summary", "Sin título"),
                    "Tipo": issue["fields"]["issuetype"]["name"] if issue["fields"].get("issuetype") else "—",
                    "Estado": issue["fields"]["status"]["name"] if issue["fields"].get("status") else "—",
                    "Prioridad": issue["fields"]["priority"]["name"] if issue["fields"].get("priority") else "—",
                    "Asignado a": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "Sin asignar",
                    "Reportado por": issue["fields"]["reporter"]["displayName"] if issue["fields"].get("reporter") else "—",
                })
            return tickets_limpios, "REAL"
        else:
            return [], "ERROR_HTTP"

    except requests.exceptions.Timeout:
        return [], "ERROR_TIMEOUT"
    except Exception as e:
        return [], "ERROR_GENERICO"


st.sidebar.title("Joran 🤖")
st.sidebar.caption("Plataforma de Operaciones Unificada")
st.sidebar.write("---")

opcion = st.sidebar.radio(
    "Selecciona una plataforma:",
    ["📊 Panel de control general", "📋 Gestión de JIRAs Real", "💽 Entorno FinIQ"],
    label_visibility="visible"
)

if opcion == "📊 Panel de control general":
    st.title("📊 Panel de Estado General")
    st.write("Bienvenida a Joran. Selecciona una opción en el menú de la izquierda para operar con tus plataformas.")

elif opcion == "📋 Gestión de JIRAs Real":
    st.title("📋 Conector Oficial de JIRA (Datos en Vivo)")

    # --- FILTRO DE TIPO ---
    tipo_jira = st.radio(
        "¿Qué JIRAs quieres ver?",
        ["Todos", "Cliente", "Interno"],
        horizontal=True
    )

    estado_placeholder = st.empty()
    estado_placeholder.info("Conectando con finiq.atlassian.net...")

    def obtener_todos_los_tickets(tipo_filtro):
        auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # JQL según filtro
        if tipo_filtro == "Cliente":
            jql = "project is not EMPTY AND issueType in standardIssueTypes() ORDER BY updated DESC"
        elif tipo_filtro == "Interno":
            jql = "project is not EMPTY AND issueType in subTaskIssueTypes() ORDER BY updated DESC"
        else:
            jql = "project is not EMPTY ORDER BY updated DESC"

        todos_los_tickets = []
        start_at = 0
        page_size = 100  # Máximo permitido por Jira

        while True:
            payload = {
                "jql": jql,
                "startAt": start_at,
                "maxResults": page_size,
                "fields": ["summary", "status", "issuetype", "priority", "project", "assignee", "reporter"]
            }

            try:
                response = requests.post(
                    f"{JIRA_URL}/rest/api/3/search/jql",
                    json=payload,
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
                        "Proyecto": issue["fields"].get("project", {}).get("name", "—"),
                        "Resumen": issue["fields"].get("summary", "Sin título"),
                        "Tipo": issue["fields"]["issuetype"]["name"] if issue["fields"].get("issuetype") else "—",
                        "Estado": issue["fields"]["status"]["name"] if issue["fields"].get("status") else "—",
                        "Prioridad": issue["fields"]["priority"]["name"] if issue["fields"].get("priority") else "—",
                        "Asignado a": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else "Sin asignar",
                        "Reportado por": issue["fields"]["reporter"]["displayName"] if issue["fields"].get("reporter") else "—",
                    })

                start_at += page_size

                # Si ya tenemos todos, paramos
                if start_at >= total:
                    break

            except requests.exceptions.Timeout:
                return [], "ERROR_TIMEOUT"
            except Exception as e:
                return [], "ERROR_GENERICO"

        return todos_los_tickets, "REAL"

    lista_tickets, origen = obtener_todos_los_tickets(tipo_jira)

    if origen == "REAL" and lista_tickets:
        estado_placeholder.success(f"✅ {len(lista_tickets)} tickets sincronizados con Atlassian.")

        import pandas as pd
        df = pd.DataFrame(lista_tickets)

        st.write("**Selecciona una fila para ver el detalle completo:**")
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
            st.subheader(f"📄 Detalle completo: {ticket_id}")

            with st.spinner(f"Cargando detalle de {ticket_id}..."):
                url_detalle = f"{JIRA_URL}/rest/api/3/issue/{ticket_id}?expand=renderedFields,changelog,attachment,comment"
                auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN)
                headers = {"Accept": "application/json"}

                try:
                    r = requests.get(url_detalle, headers=headers, auth=auth, timeout=10)
                    if r.status_code == 200:
                        issue = r.json()
                        fields = issue.get("fields", {})

                        col1, col2, col3 = st.columns(3)
                        col1.metric("Estado", fields.get("status", {}).get("name", "—"))
                        col2.metric("Tipo", fields.get("issuetype", {}).get("name", "—"))
                        col3.metric("Prioridad", fields.get("priority", {}).get("name", "—") if fields.get("priority") else "—")

                        st.markdown(f"### {fields.get('summary', 'Sin título')}")

                        col4, col5 = st.columns(2)
                        assignee = fields.get("assignee")
                        reporter = fields.get("reporter")
                        col4.write(f"👤 **Asignado a:** {assignee['displayName'] if assignee else 'Sin asignar'}")
                        col5.write(f"📝 **Reportado por:** {reporter['displayName'] if reporter else '—'}")

                        col6, col7 = st.columns(2)
                        col6.write(f"📅 **Creado:** {fields.get('created', '—')[:10] if fields.get('created') else '—'}")
                        col7.write(f"🔄 **Actualizado:** {fields.get('updated', '—')[:10] if fields.get('updated') else '—'}")

                        st.write("---")
                        st.write("**📋 Descripción:**")
                        descripcion = fields.get("description")
                        if descripcion and descripcion.get("content"):
                            texto = []
                            for bloque in descripcion["content"]:
                                for item in bloque.get("content", []):
                                    if item.get("type") == "text":
                                        texto.append(item.get("text", ""))
                            st.write(" ".join(texto) if texto else "_Sin descripción_")
                        else:
                            st.write("_Sin descripción_")

                        adjuntos = fields.get("attachment", [])
                        if adjuntos:
                            st.write("---")
                            st.write(f"**📎 Adjuntos ({len(adjuntos)}):**")
                            for adj in adjuntos:
                                nombre = adj.get("filename", "archivo")
                                url_adj = adj.get("content", "")
                                mime = adj.get("mimeType", "")
                                if mime.startswith("image/"):
                                    try:
                                        img_response = requests.get(url_adj, auth=HTTPBasicAuth(JIRA_EMAIL, JIRA_TOKEN), timeout=10)
                                        if img_response.status_code == 200:
                                            st.image(img_response.content, caption=nombre, use_column_width=True)
                                    except:
                                        st.write(f"🖼️ No se pudo cargar la imagen: {nombre}")
                                else:
                                    st.markdown(f"📄 [{nombre}]({url_adj})")

                        comentarios = fields.get("comment", {}).get("comments", [])
                        if comentarios:
                            st.write("---")
                            st.write(f"**💬 Comentarios ({len(comentarios)}):**")
                            for com in comentarios:
                                autor = com.get("author", {}).get("displayName", "Desconocido")
                                fecha = com.get("created", "")[:10]
                                cuerpo = com.get("body", {})
                                texto_com = []
                                if isinstance(cuerpo, dict):
                                    for bloque in cuerpo.get("content", []):
                                        for item in bloque.get("content", []):
                                            if item.get("type") == "text":
                                                texto_com.append(item.get("text", ""))
                                texto_final = " ".join(texto_com) if texto_com else "_Sin texto_"
                                with st.expander(f"💬 {autor} — {fecha}"):
                                    st.write(texto_final)

                        changelog = issue.get("changelog", {}).get("histories", [])
                        if changelog:
                            st.write("---")
                            st.write(f"**🕓 Historial de cambios ({len(changelog)}):**")
                            with st.expander("Ver historial completo"):
                                for cambio in reversed(changelog):
                                    autor = cambio.get("author", {}).get("displayName", "—")
                                    fecha = cambio.get("created", "")[:10]
                                    for item in cambio.get("items", []):
                                        campo = item.get("field", "—")
                                        antes = item.get("fromString", "—")
                                        despues = item.get("toString", "—")
                                        st.write(f"• `{fecha}` **{autor}** cambió **{campo}**: _{antes}_ → _{despues}_")

                        st.write("---")
                        st.markdown(f"🔗 [Abrir en Jira]({JIRA_URL}/browse/{ticket_id})")

                    else:
                        st.error(f"Error al cargar el detalle: HTTP {r.status_code}")

                except Exception as e:
                    st.error(f"Error de conexión: {e}")

    elif origen == "REAL" and not lista_tickets:
        estado_placeholder.warning("Conexión OK pero sin tickets visibles para tu usuario.")
    else:
        estado_placeholder.warning(f"No se pudo conectar ({origen}).")

   
        

elif opcion == "💽S Entorno FinIQ":
    st.title("💽 Euroconnect Equity Structures")
    st.write("Configuración del entorno de testeo:")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("On behalf Of", value="DESHAW")
        st.selectbox("Format", ["Note", "Certificate"])
    with col2:
        st.selectbox("Coupon Type", ["Conditional with memory", "Fixed"])
        st.checkbox("Memory Coupon", value=True)