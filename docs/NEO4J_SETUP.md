# Como instalar e configurar o Neo4j (Fase 2)

Este guia permite subir o Neo4j, configurar o projeto e rodar ingestão, query e o verificador de requisitos da Fase 2.

---

## 1. Instalar e subir o Neo4j

Escolha **uma** das opções abaixo.

### Opção A — Docker (recomendado)

1. **Instale o Docker** (se ainda não tiver): [Docker Desktop para Windows](https://docs.docker.com/desktop/install/windows-install/).

2. **Suba o Neo4j** em um container:

   ```powershell
   docker run -d --name neo4j-nasa -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/sua_senha_aqui neo4j:5
   ```

   Troque `sua_senha_aqui` por uma senha forte (ex.: `MeuNeo4j2024`).  
   - Porta **7474**: interface web (Browser).  
   - Porta **7687**: Bolt (conexão do Python).

3. **Verificar se está rodando:**

   ```powershell
   docker ps
   ```

   Deve aparecer o container `neo4j-nasa` com status “Up”.

4. **(Opcional)** Abra no navegador: **http://localhost:7474**. Login: `neo4j` / senha que você definiu. Não é obrigatório para o projeto; o Python usa só a porta 7687.

---

### Opção B — Neo4j Desktop (Windows)

1. Baixe e instale: [Neo4j Desktop](https://neo4j.com/download/).
2. Crie um novo projeto e adicione um banco **Local DB** (Neo4j 5.x).
3. Defina a **senha** do usuário `neo4j` na primeira inicialização.
4. Clique em **Start** no banco. Por padrão:
   - Bolt: `bolt://localhost:7687`
   - Browser: `http://localhost:7474`

---

### Opção C — Neo4j Aura (nuvem)

1. Crie uma conta em [Neo4j Aura](https://neo4j.com/cloud/aura/) e crie uma instância **Free**.
2. Anote **URI** (Bolt), **usuário**, **senha** e, se for usar a API HTTP, a **API URL** e o **Instance ID**.

**Campos típicos no Aura:**

| Campo        | Exemplo / descrição |
|-------------|----------------------|
| **URI**     | `neo4j+s://<INSTANCE_ID>.databases.neo4j.io` — usada pelo driver Bolt (Python). |
| **API URL** | `https://<INSTANCE_ID>.databases.neo4j.io/db/<INSTANCE_ID>/query/v2` — para chamadas REST (Cypher via HTTP). |
| **Instance ID** | Identificador da instância (ex.: `2db5009a`); aparece no URI e na API URL. |
| **database** | No Aura, use `""` em `configs/local.yaml` para o banco padrão do servidor (evita `DatabaseNotFound`). |

3. No projeto, configure em `configs/local.yaml`: `neo4j.uri`, `neo4j.user`, `neo4j.password` e, se necessário, `neo4j.database` (vazio para padrão).

---

## 2. Configurar o projeto

A aplicação lê usuário e senha do Neo4j destas formas (override na ordem abaixo):

1. **`configs/local.yaml`** (recomendado; arquivo **não versionado**, em `.gitignore`): defina `neo4j.user` e `neo4j.password` (e, se for Aura, `neo4j.uri`). Copie de `configs/local.yaml.example` se o arquivo não existir.
2. Variável de ambiente **`NEO4J_PASSWORD`** (senha); usuário vem do config (`default.yaml` ou `local.yaml`).
3. Campo **`neo4j.password`** em `configs/default.yaml` (evite versionar senha).

**Recomendado (senha fora do arquivo versionado):**

No **PowerShell** (sessão atual):

```powershell
$env:NEO4J_PASSWORD = "sua_senha_aqui"
```

Substitua `sua_senha_aqui` pela **mesma senha** usada no Neo4j (Docker: a que você colocou em `NEO4J_AUTH`; Desktop/Aura: a definida no banco).

Para deixar a variável definida de forma persistente no usuário (Windows):

```powershell
[System.Environment]::SetEnvironmentVariable("NEO4J_PASSWORD", "sua_senha_aqui", "User")
```

Depois, feche e abra o terminal/IDE para carregar a variável.

**Alternativa (apenas para teste local):** edite `configs/default.yaml` e preencha a senha na seção `neo4j`:

```yaml
neo4j:
  uri: bolt://localhost:7687
  user: neo4j
  password: "sua_senha_aqui"   # só para teste; não commitar
  database: neo4j
  # ...
```

Se usar **Neo4j Aura**, altere também o `uri` para o valor fornecido (ex.: `neo4j+s://xxxx.databases.neo4j.io`).

---

## 3. Conferir conectividade (opcional)

Na raiz do projeto:

```powershell
cd c:\Users\Administrator\Documents\rag-nasa
python -c "from src.graphrag.neo4j_store import get_driver; from src.ingestion.config_loader import load_config; d = get_driver(load_config()); d.verify_connectivity(); print('OK: Neo4j conectado'); d.close()"
```

Se aparecer **"OK: Neo4j conectado"**, o Neo4j está acessível e a senha está correta.

---

## 4. Rodar a ingestão

Com o Neo4j no ar e a senha configurada:

```powershell
cd c:\Users\Administrator\Documents\rag-nasa
python scripts/run_neo4j_ingest.py
```

Saída esperada (exemplo):

```
... [INFO] ... Ingestão Neo4j: 699 chunks inseridos.
Ok: 699 chunks ingeridos no Neo4j. Use scripts/run_neo4j_query.py para consultar.
```

O número de chunks depende dos arquivos em `data/chunks/*.jsonl` (Fase 1).

---

## 5. Rodar uma query

```powershell
python scripts/run_neo4j_query.py "Qual a diferença entre Verificação e Validação?"
```

Ou com log em `log/`:

```powershell
python scripts/run_neo4j_query.py "Verification and Validation" --log-dir log
```

A saída é o **contexto** (trechos do Handbook recuperados pela busca full-text).

---

## 6. Rodar o verificador de requisitos

Sem a query de referência (só checagens de config, scripts e índice):

```powershell
python scripts/run_phase2_requirements_verifier.py
```

Com a **query de referência** (“Verificação vs Validação”):

```powershell
python scripts/run_phase2_requirements_verifier.py --run-reference-query
```

Relatórios gerados em:

- `log/phase2_requirements_verification_<timestamp>.json`
- `log/phase2_requirements_verification_<timestamp>.txt`

Com Neo4j rodando, senha configurada e ingestão feita, o esperado é **0 FAIL** (e menos SKIP); FR-2.2.1, FR-2.1.2 e FR-2.2.3 passam quando o banco está acessível e com chunks.

---

## 7. Resumo rápido (copy-paste)

**Primeira vez (Docker + senha + ingestão + verificador):**

```powershell
# 1) Subir Neo4j (troque sua_senha_aqui)
docker run -d --name neo4j-nasa -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=neo4j/sua_senha_aqui neo4j:5

# 2) Senha no ambiente (use a mesma senha)
$env:NEO4J_PASSWORD = "sua_senha_aqui"

# 3) Ir para o projeto
cd c:\Users\Administrator\Documents\rag-nasa

# 4) Ingerir chunks
python scripts/run_neo4j_ingest.py

# 5) Verificador
python scripts/run_phase2_requirements_verifier.py --run-reference-query
```

**Próximas vezes (Neo4j já instalado e rodando):**

```powershell
$env:NEO4J_PASSWORD = "sua_senha_aqui"
cd c:\Users\Administrator\Documents\rag-nasa
python scripts/run_neo4j_ingest.py   # só se tiver recriado o banco
python scripts/run_neo4j_query.py "Sua pergunta"
python scripts/run_phase2_requirements_verifier.py --run-reference-query
```

---

## 8. Parar o Neo4j (Docker)

```powershell
docker stop neo4j-nasa
```

Para iniciar de novo:

```powershell
docker start neo4j-nasa
```

Para remover o container (os dados do banco são perdidos):

```powershell
docker stop neo4j-nasa
docker rm neo4j-nasa
```

---

## 9. Problemas comuns

| Sintoma | O que fazer |
|--------|--------------|
| `Neo4j inacessível` / `ServiceUnavailable` | Neo4j está rodando? `docker ps` ou verifique o Neo4j Desktop. Porta 7687 liberada? |
| `Neo4j password não definido` | Defina `NEO4J_PASSWORD` no PowerShell ou preencha `neo4j.password` em `configs/default.yaml`. |
| `Authentication failed` | A senha no ambiente/config deve ser **exatamente** a do Neo4j (Docker: a usada em `NEO4J_AUTH`). |
| `Nenhum chunk no Neo4j` | Rode antes `python scripts/run_neo4j_ingest.py`. Confira se existe `data/chunks/*.jsonl` (Fase 1). |
| `Nenhum arquivo .jsonl em data/chunks` | Conclua a Fase 1: `python run_ingestion.py` (com PDF ou Markdown já gerado). |

---

*Referência: [FASE2_GRAPHRAG.md](FASE2_GRAPHRAG.md), [REQUIREMENTS_FASE2.md](REQUIREMENTS_FASE2.md).*
