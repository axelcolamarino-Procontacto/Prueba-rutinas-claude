from google.cloud import bigquery
import json, uuid

client = bigquery.Client(project="procontacto-claude")

test_cases = [
    {
        "id": str(uuid.uuid4()),
        "project": "CMIV2",
        "issue_key": "CMIV2-2559",
        "issue_type": "Story",
        "sprint": "CMIB4B Sprint 8",
        "module": "Gestión de Visitas",
        "submodule": "Campo lookup Medición",
        "tc_id": "TC-01",
        "title": "Campo Medición visible en el layout de edición de una Visita",
        "test_type": "positivo",
        "preconditions": "Existir una Visita con RecordType=Editable. Usuario autenticado con FLS de lectura sobre Visit.Measurement__c.",
        "steps": ["Navegar a la visita 00000497 (RecordType Editable, 0Z5gP000000jvtNSAQ) en Backoffice", "Observar el formulario de detalle de la visita", "Verificar que el campo Medición es visible en el layout", "Hacer clic en el botón Editar de la visita", "Verificar que el campo Medición aparece como campo editable tipo lookup en el formulario"],
        "expected_result": "El campo Medición aparece visible en el layout de detalle y edición de la Visita. El campo es de tipo lookup que permite buscar registros del objeto Medición.",
        "source_description": "HU CMIV2-2559 Tarea3: Agregar campo al Page Layout de Visita en Backoffice",
    },
    {
        "id": str(uuid.uuid4()),
        "project": "CMIV2",
        "issue_key": "CMIV2-2559",
        "issue_type": "Story",
        "sprint": "CMIB4B Sprint 8",
        "module": "Gestión de Visitas",
        "submodule": "Campo lookup Medición",
        "tc_id": "TC-02",
        "title": "Asociar una Medición existente a una Visita desde Backoffice",
        "test_type": "positivo",
        "preconditions": "Existir al menos una Medición MD-00001 y una Visita Editable. Campo Medición visible en el layout.",
        "steps": ["Navegar a la visita 00000497 en Backoffice", "Hacer clic en Editar o edición inline sobre el campo Medición", "Escribir MD-00001 en el campo lookup Medición", "Seleccionar el registro MD-00001 del listado de resultados", "Hacer clic en Guardar", "Verificar que el campo Medición muestra MD-00001 en el detalle"],
        "expected_result": "La visita queda guardada con el campo Medición apuntando a MD-00001. El campo muestra el nombre de la Medición como hipervínculo clickeable.",
        "source_description": "HU CMIV2-2559 Tarea5: Validar asociación visita-medición en Backoffice",
    },
    {
        "id": str(uuid.uuid4()),
        "project": "CMIV2",
        "issue_key": "CMIV2-2559",
        "issue_type": "Story",
        "sprint": "CMIB4B Sprint 8",
        "module": "Gestión de Visitas",
        "submodule": "Campo lookup Medición",
        "tc_id": "TC-03",
        "title": "Visita aparece en lista relacionada Visitas del registro Medición",
        "test_type": "positivo",
        "preconditions": "TC-02 ejecutado correctamente: visita 00000497 tiene Medición = MD-00001.",
        "steps": ["Navegar al registro Medición MD-00001 a6YgP0000005GCDUA2", "Desplazarse hacia abajo buscando la sección lista relacionada Visitas", "Verificar que la lista relacionada Visitas existe y es visible", "Verificar que la visita 00000497 aparece en dicha lista"],
        "expected_result": "El registro MD-00001 muestra sección de lista relacionada Visitas que contiene la visita 00000497.",
        "source_description": "HU CMIV2-2559 Tarea7: Validar que la visita aparece en Visitas asociadas de la medición vinculada",
    },
    {
        "id": str(uuid.uuid4()),
        "project": "CMIV2",
        "issue_key": "CMIV2-2559",
        "issue_type": "Story",
        "sprint": "CMIB4B Sprint 8",
        "module": "Gestión de Visitas",
        "submodule": "Campo lookup Medición",
        "tc_id": "TC-04",
        "title": "Guardar Visita sin valor en campo Medición - campo opcional",
        "test_type": "negativo",
        "preconditions": "Existir una Visita Editable. Campo Medición visible en el layout.",
        "steps": ["Navegar a la visita 00000495 0Z5gP000000ju2sSAA en Backoffice", "Hacer clic en Editar", "Verificar que el campo Medición está vacío", "No completar el campo Medición", "Hacer clic en Guardar", "Verificar que la visita se guarda correctamente sin error de validación"],
        "expected_result": "La visita se guarda exitosamente sin valor en Medición. No aparece mensaje de error. El campo Medición muestra vacío en el detalle.",
        "source_description": "HU CMIV2-2559: Campo lookup no requerido - verificar que no hay validation rule que lo obligue",
    },
    {
        "id": str(uuid.uuid4()),
        "project": "CMIV2",
        "issue_key": "CMIV2-2559",
        "issue_type": "Story",
        "sprint": "CMIB4B Sprint 8",
        "module": "Gestión de Visitas",
        "submodule": "Campo lookup Medición",
        "tc_id": "TC-05",
        "title": "Búsqueda en campo lookup Medición muestra resultados del objeto Medición",
        "test_type": "borde",
        "preconditions": "Campo Medición visible en el layout. Existen registros MD-00000 y MD-00001.",
        "steps": ["Navegar a la visita 00000497 en modo edición", "Hacer clic en el campo Medición para activarlo", "Escribir MD en el campo de búsqueda del lookup", "Verificar que aparecen sugerencias con registros del objeto Medición", "Verificar que se muestran MD-00000 y MD-00001 como opciones", "Seleccionar MD-00000 y verificar que el campo se actualiza"],
        "expected_result": "El campo lookup muestra resultados del objeto Medición al escribir. Los registros pertenecen a Measurement__c y se puede seleccionar cualquiera.",
        "source_description": "HU CMIV2-2559: Verificar que el lookup apunta correctamente al objeto Measurement__c",
    },
]

for tc in test_cases:
    title = tc["title"]
    expected = tc["expected_result"]
    text_embed = title + ": " + expected
    tc_id = tc["tc_id"]

    # Build safe query
    def esc(s): return s.replace("'", "\\'") if s else ""

    q = """
    INSERT INTO `procontacto-claude.qa_agent.test_cases`
      (id, project, issue_key, issue_type, sprint, module, submodule,
       tc_id, title, test_type, preconditions, steps, expected_result,
       source_description, embedding, status, created_at, updated_at)
    SELECT
      @id, @project, @issue_key, @issue_type, @sprint, @module, @submodule,
      @tc_id, @title, @test_type, @preconditions, @steps, @expected_result,
      @source_description, ml_generate_embedding_result,
      'generated', CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
    FROM ML.GENERATE_EMBEDDING(
      MODEL `procontacto-claude.qa_agent.embedding_model`,
      (SELECT @embed_text AS content)
    )
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("id", "STRING", tc["id"]),
            bigquery.ScalarQueryParameter("project", "STRING", tc["project"]),
            bigquery.ScalarQueryParameter("issue_key", "STRING", tc["issue_key"]),
            bigquery.ScalarQueryParameter("issue_type", "STRING", tc["issue_type"]),
            bigquery.ScalarQueryParameter("sprint", "STRING", tc["sprint"]),
            bigquery.ScalarQueryParameter("module", "STRING", tc["module"]),
            bigquery.ScalarQueryParameter("submodule", "STRING", tc["submodule"]),
            bigquery.ScalarQueryParameter("tc_id", "STRING", tc["tc_id"]),
            bigquery.ScalarQueryParameter("title", "STRING", tc["title"]),
            bigquery.ScalarQueryParameter("test_type", "STRING", tc["test_type"]),
            bigquery.ScalarQueryParameter("preconditions", "STRING", tc["preconditions"]),
            bigquery.ArrayQueryParameter("steps", "STRING", tc["steps"]),
            bigquery.ScalarQueryParameter("expected_result", "STRING", tc["expected_result"]),
            bigquery.ScalarQueryParameter("source_description", "STRING", tc["source_description"]),
            bigquery.ScalarQueryParameter("embed_text", "STRING", text_embed),
        ]
    )

    job = client.query(q, job_config=job_config)
    job.result()
    print(f"OK {tc_id}: {title[:55]}")

print("\n5 TCs insertados en BigQuery correctamente.")
