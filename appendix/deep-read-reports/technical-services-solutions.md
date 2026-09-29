> **Provenance.** Deep-read of `databricks-solutions/technical-services-solutions` @ `41fa465`, written by a research sub-agent during this study and kept verbatim, apart from local paths normalised to `<clone-root>/`. Its CONFIRMED / SUSPECTED labels are the agent's. The claims I re-verified myself, and how, are listed in [`README.md`](README.md); anything not listed there I have not independently checked.

# technical-services-solutions — deep-read technical report

Repository: `github.com/databricks-solutions/technical-services-solutions`. I read the local clone at commit `41fa465` ("Merge pull request #86 … feat/new-track-folders", 2026-09-28). The clone is shallow, so it has only one commit. Every `path:line` citation below is relative to the repository root. "(inferred)" marks a claim I reasoned out but did not execute. Each item in §8 is labelled **CONFIRMED** (read in code and, where noted, reproduced) or **SUSPECTED**.

To gather the evidence I ran the following read-only steps. None of them modified the repository.

* I enumerated every file with `find` (380 files).
* I unzipped the Power BI sample reports into the scratchpad.
* I installed `sqlglot 26.33` (the version `app_for_conversions/requirements.txt` pins) and PySpark 4.0.1 in a scratch virtualenv. I then ran the converter's post-processing functions against crafted SQL and tested Spark's JSON coercion.
* I ran `tsc -b` without a tsconfig.
* I fetched `terraform-aws-modules/vpc v5.1.1` source, the azurerm v4.50 `databricks_workspace` docs, the Databricks API and bundle docs, and the Lakeflow Connect docs to settle disputed behaviour.

---

## 1. What it is (customer framing)

This is Databricks' **Shared Technical Services "field accelerator" monorepo**. It holds example code the field team uses to stand up and harden customer platforms quickly. The accelerators are:

* cloud-specific Terraform, Pulumi and PowerShell for **secure workspace deployment** on AWS, Azure and GCP (BYO-VPC, VNet injection, PrivateLink, PSC, serverless NCC, Unity Catalog bootstrap);
* **governance** playbooks: Unity Catalog ABAC with governed tags, Data Classification, row filters and column masks, and a user-ownership inventory for identity migrations;
* **data engineering** bundles: Lakeflow Connect SQL Server CDC, a network pre-flight validator, and schema-drift handling with Spark Declarative Pipelines;
* **warehousing and BI**: a UC metric-view semantic layer, and an LLM-powered Power BI → AI/BI dashboard converter delivered as a Databricks App;
* **CI/CD** reference projects: an end-to-end DAB plus four CI systems, an AI "skill" that migrates UI-built assets into bundles, and a Lakebase + Apps template.

Everything ships **as-is, without support** (`README.md:47-54`, `NOTICE.md:1-3`). The code is best treated as well-commented starting points, not production modules. The newest top-level "track" folders (`aibi-migration/`, `dw-migration/`, `genie/`, `production-readiness/`, `unified-governance/`) are empty placeholders.

---

## 2. Inventory

Maturity scale: **substantial** means runnable, multi-file, with docs. **Partial** means runnable but narrow or thin. **Stub** means a README or keep-file only. The LOC counts in the Tech column exclude docs.

| Project | Path | Customer problem | Tech | Maturity |
|---|---|---|---|---|
| AWS BYOVPC (deprecated) | `workspace-setup/terraform-examples/aws/aws-byovpc` | Workspace in customer VPC, attach/create metastore | Terraform (databricks ~1.84, aws 5–6, terraform-aws-modules/vpc 5.1.1); 550 LOC | substantial (legacy) |
| AWS BYOVPC + UC (recommended) | `…/aws/aws-byovpc-uc` | Same, plus a catalog with its own bucket, IAM role, storage credential and external location, plus a test cluster | Terraform; 818 LOC | substantial |
| AWS classic PrivateLink | `…/aws/aws-byovpc-classic-privatelink` | Back-end PrivateLink (REST + SCC relay), restrictive egress, optional fully-private VPC | Terraform; 900 LOC | substantial |
| AWS serverless + NCC | `…/aws/aws-serverless-ncc` | Serverless-only workspace; private serverless→S3 path; UC external location plus grants | Terraform + bash (`aws`, `jq`, `databricks` CLI); 1,138 LOC | substantial |
| Azure VNet injection (deprecated) | `…/azure/azure-vnet-injection` | VNet-injected workspace with NPIP and metastore | Terraform (azurerm ~4.50); 427 LOC | substantial (legacy) |
| Azure VNet injection + UC (recommended) | `…/azure/azure-vnet-injection-uc` | Adds access connector, ADLS, storage credential, external location, catalog and a policy-bound cluster | Terraform; 655 LOC | substantial |
| Azure PrivateLink (classic) | `…/azure/azure-privatelink-classic` | Back-end PL plus DBFS private endpoints, service-endpoint policy, NCC to DBFS | Terraform + azapi; 868 LOC | substantial |
| GCP BYOVPC standalone / shared VPC | `…/gcp/gcp-byovpc-standalone`, `…/gcp/gcp-byovpc-shared-vpc` | Customer-managed VPC (new or shared host project) | Terraform; ~170 LOC each | partial |
| GCP classic PSC | `…/gcp/gcp-byovpc-classic-psc` | Back-end PSC (REST + relay) plus private Cloud DNS | Terraform; 511 LOC | substantial |
| Pulumi Azure hybrid | `workspace-setup/pulumi-examples/azure/azure-hybrid` | Same outcome as the Terraform examples, in Python IaC | Pulumi azure-native; 55 LOC | partial |
| Managed VNet → VNet injection | `workspace-setup/powershell-examples/managed-vnet-to-vnet-injection` | Move an existing workspace off a managed VNet | PowerShell + `az` + ARM export/redeploy; 752 LOC | substantial |
| S3 policy migration (temp tool) | `workspace-setup/temp-tools/S3 Policy Migration` | Which S3 buckets back UC external locations (guidance only) | Terraform data sources; 224 LOC | partial |
| AIM user-ownership inventory | `workspace-setup/aim-user-ownership-inventory` | Before deleting ex-employees, list what they own | Notebook + Databricks SDK; 519 LOC | substantial |
| Unity Catalog ABAC | `data-governance/unity-catalog-abac` | Tag-driven masking and RLS instead of per-table rules | SQL + Terraform (`databricks_policy_info`, `databricks_tag_policy`); 283 LOC | substantial (demo) |
| UC Business Semantics | `data-warehousing/dbrx-business-semantics` | One governed KPI layer for BI and Genie | 4 notebooks: metric views (YAML 1.1), materialization, Genie and dashboard JSON | substantial (demo) |
| Power BI → AI/BI converter | `data-warehousing/pbi-aibi-converter` | Migrate a PBI report estate to AI/BI dashboards | Streamlit on Databricks Apps, OpenAI-compatible Model Serving, sqlglot, SDK; 5,438 LOC | substantial |
| Lakeflow Connect SQL Server CDC | `data-engineering/lakeflow-connect/sql-server-cdc` | Managed CDC from SQL Server into UC | DAB YAML + agent RUNBOOK; 140 LOC | partial |
| Lakeflow CDC source validator | `data-engineering/lakeflow-connect/lakeflow-connectivity-validator` | "Why can't Databricks reach my DB?" pre-flight | Notebook (DNS/TCP/TLS, pure-Python TDS login) | substantial |
| SDP schema evolution | `data-engineering/sdp-evolution` | Survive renames, type changes and new columns without a full refresh | DAB + `pyspark.pipelines` + Auto Loader rescue; 346 LOC | substantial (demo) |
| Customer 360 + Genie (CI/CD) | `core-platform/cicd/customer-360-lakehouse-genie` | One bundle for pipeline, metric view, dashboard and Genie, with 4 CI systems | DAB (`engine: direct`), SDP, GH Actions / ADO / GitLab / Jenkins; 1,133 LOC | substantial |
| dabs-migrator skill | `core-platform/cicd/dabs-migrator` | Turn UI-built assets into a bundle repo with CI | Agent skill (SKILL.md plus 30 resource refs and 6 CI refs), 14.6k-line bundle schema, release workflow | substantial (prompt-ware) |
| OrderFlow (Apps + Lakebase) | `core-platform/cicd/orderflow-app-lakebase` | Reference OLTP app plus lakehouse analytics as one bundle | DAB (postgres_* resources), FastAPI + React, psycopg, SDP; 1,764 LOC | substantial |
| Track placeholders | `aibi-migration/`, `dw-migration/`, `genie/`, `production-readiness/`, `unified-governance/` | Future home for migrations, Genie, hardening, governance | README "New work in this track lands here." | stub |
| Legacy category shells | `core-platform/`, `data-governance/`, `genai-ml/`, `launch-accelerator/` READMEs | Category index | one-line README plus `.gitkeep`/`.getkeep` | stub |

---

## 3. Deep dives

### 3.1 `workspace-setup/terraform-examples` (deepest)

**Philosophy.** The examples are deliberately "scenario-based … minimal modularization … production-ready … quick start" (`workspace-setup/terraform-examples/README.md:23-28`). Each scenario is one flat root module split by concern (`network.tf`, `credential.tf`, `workspace.tf`, `metastore.tf`, `unity_catalog.tf`, …), not a module library. The only external module is `terraform-aws-modules/vpc` (`aws-byovpc-uc/tf/network.tf:1-4`). The recurring provider pattern is two Databricks provider aliases:

* an **account** provider (`https://accounts.cloud.databricks.com`, `accounts.azuredatabricks.net`, `accounts.gcp.databricks.com`);
* a **workspace** provider whose `host` is a *resource attribute* of the workspace just created, for example `aws-byovpc-uc/tf/providers.tf:22-33`.

**Clouds and what each scenario provisions**

| Scenario | Network | Identity / auth | UC objects | Notable security controls |
|---|---|---|---|---|
| aws-byovpc(-uc) | VPC module (private, public and intra subnets), single or per-AZ NAT (`-uc/tf/network.tf:12-15`), S3 gateway plus STS/Kinesis interface endpoints, dedicated SG (443, 3306, 2443, 5432, 8443-8451 egress; self ingress) (`-uc/tf/security_group.tf:1-48`) | Cross-account role from `databricks_aws_assume_role_policy` (external ID = account ID) plus `databricks_aws_crossaccount_policy` (`-uc/tf/credential.tf:1-21`); SP via OAuth M2M (`-uc/tf/providers.tf:16-27`) | Metastore create/attach with region precondition (`-uc/tf/metastore.tf:15-27`); optional catalog on its own bucket via storage credential, IAM role and external location (`-uc/tf/unity_catalog.tf:27-128`) | Default SG locked down (`network.tf:26-30`); UC bucket public access block (`unity_catalog.tf:96-104`); `databricks_account_id` marked sensitive |
| aws-byovpc-classic-privatelink | `standard` (NAT), `fully_private` (no IGW/NAT, endpoint subnet) or `custom` (BYO IDs) (`tf/variables.tf:50-62`) | Same cross-account role | Metastore create/attach | Back-end PL endpoints for REST and SCC relay with region service maps (`tf/privatelink.tf:80-99`, `variables.tf:182-308`); PL SG allows only 443/6666/2443/5432/8443-8451 from the workspace SG (`privatelink.tf:1-61`); workspace SG egress restricted to the VPC CIDR plus the S3 prefix list (`network.tf:103-135`); PAS `private_access_level = "ACCOUNT"` (`workspace.tf:51-57`) |
| aws-serverless-ncc | None in the customer account: `compute_mode = "SERVERLESS"` (`tf/workspace.tf:13-21`) | Admin via `databricks_mws_permission_assignment` (`workspace.tf:47-57`) | Metastore create/lookup by ID, name or region (`metastore.tf:7-57`); UC role, storage credential and external location plus **authoritative** `databricks_grants` (`credential.tf:78-95`, `external_location.tf:37-54`) | NCC plus S3 private-endpoint rule, `aws:SourceVpce` bucket policy, polling scripts (`tf/s3_endpoint.tf:13-287`) |
| azure-vnet-injection(-uc) | Delegated host/container subnets, NSG, zonal NAT GW, `default_outbound_access_enabled = false` (`-uc/tf/network.tf:46-129`) | Azure CLI or ARM SP; admin via `mws_permission_assignment` (`-uc/tf/databricks.tf:27-40`) | Metastore owned by a **group** `<name>-admins` (`-uc/tf/databricks.tf:44-71`); access connector (system MI), ADLS Gen2, Blob Data Contributor, storage credential, external location, catalog (`-uc/tf/unity_catalog.tf:1-81`) | `no_public_ip = true` (`databricks.tf:16`); storage TLS1.2, infrastructure encryption, no public nested items (`unity_catalog.tf:22-25`); cluster bound to the built-in "Personal Compute" policy (`cluster.tf:13-44`) |
| azure-privatelink-classic | VNet with public, private and PL subnets; optional NAT; NSG outbound only to AAD and Front Door (`tf/network.tf:62-97`) | `azure_tenant_id` from client config | Optional metastore assignment only (`databricks.tf:59-67`) | `network_security_group_rules_required = "NoAzureDatabricksRules"`, DBFS storage firewall plus access connector (`databricks.tf:34-39`); PE `databricks_ui_api` plus DBFS blob/dfs PEs and private DNS (`pe_backend.tf`, `pe_dbfs.tf`, `dns_zones.tf`); **service-endpoint policy** allowing only `/services/Azure/Databricks` plus a listed allow-list (`service_endpoint_policy.tf:19-41`); NCC PE rules to DBFS auto-approved via azapi (`ncc.tf:46-108`) |
| gcp-byovpc-standalone / shared-vpc | New VPC, subnet, router and NAT, or data lookups of a host-project VPC (`shared-vpc/network.tf:14-23`) | GSA impersonation (`providers.tf:6-17`); admin by adding a workspace-level user to `admins` (`databricks.tf:38-54`) | Optional metastore assignment (shared-vpc) | Private Google Access (`standalone/network.tf:24`) |
| gcp-byovpc-classic-psc | Node subnet plus PSC subnet; optional NAT (`tf/network.tf:19-59`) | `auth_type = "google-id"` (`tf/providers.tf:15`) | Optional metastore assignment | Two PSC forwarding rules to Databricks service attachments (`tf/psc.tf:21-56`); private zone `gcp.databricks.com.` with 3 A records (`tf/dns.tf:23-69`); PAS (`databricks.tf:41-47`) |

**Code trace for the AWS UC path (the canonical flow).** The dependency chain runs in this order:

1. IAM cross-account role and policy.
2. `time_sleep` of 30 s for IAM propagation (`aws-byovpc-uc/tf/workspace.tf:1-4`).
3. `databricks_mws_credentials`, `databricks_mws_storage_configurations` (root bucket plus the Databricks-generated bucket policy, `root_s3_bucket.tf:19-31`) and `databricks_mws_networks`.
4. `databricks_mws_workspaces` (`workspace.tf:20-30`).
5. `time_sleep` of 120 s.
6. Metastore assignment (`metastore.tf:15-27`).
7. The workspace-scoped provider then creates the **storage credential first**, so its `external_id` exists. The IAM trust policy is generated from that external ID (the "self-assuming role" pattern).
8. A 60 s IAM propagation wait, then the external location, then the catalog with `storage_root` = external location URL.

Excerpt (`workspace-setup/terraform-examples/aws/aws-byovpc-uc/tf/unity_catalog.tf:27-47`):

```hcl
# Storage Credential (created before role): https://registry.terraform.io/providers/databricks/databricks/latest/docs/guides/unity-catalog#configure-external-locations-and-credentials
resource "databricks_storage_credential" "uc_storage_cred" {
  count    = var.new_catalog ? 1 : 0
  provider = databricks.workspace
  name     = local.uc_storage_credential_name
  aws_iam_role {
    role_arn = "arn:aws:iam::${var.aws_account_id}:role/${local.uc_iam_role}"
  }
  depends_on = [databricks_metastore_assignment.this]
}

# Unity Catalog Trust Policy - Data Source
data "databricks_aws_unity_catalog_assume_role_policy" "unity_catalog" {
  count                 = var.new_catalog ? 1 : 0
  provider              = databricks.workspace
  aws_account_id        = var.aws_account_id
  aws_partition         = "aws"
  role_name             = local.uc_iam_role
  unity_catalog_iam_arn = "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL"
  external_id           = databricks_storage_credential.uc_storage_cred[0].aws_iam_role[0].external_id
}
```

**Serverless NCC and S3 (the hardest wiring in the repo).** The Databricks API returns an S3 private-endpoint rule before AWS has created the VPCE. It ignores `enabled=true` at create time, and the rule only reaches ESTABLISHED after a bucket policy names the VPCE (`aws-serverless-ncc/README.md:242-257`). The code handles this in four moves:

1. It creates the rule `enabled=false` with `ignore_changes=[enabled, account_id]` (`s3_endpoint.tf:13-43`).
2. It polls for `vpc_endpoint_id` with a `null_resource` and the CLI (`s3_endpoint.tf:50-66`, `scripts/wait-for-vpc-endpoint.sh`).
3. It re-reads the NCC data source. A `coalesce(rule.vpc_endpoint_id, lookup)` keeps the value *unknown at plan time*, so the bucket policy converges in one apply (`s3_endpoint.tf:77-109`).
4. It polls for ESTABLISHED and PATCHes `enabled` (`s3_endpoint.tf:268-287`, `scripts/enable-s3-rule.sh:29-54`).

Merge mode snapshots and restores any pre-existing bucket policy through a destroy-time provisioner (`s3_endpoint.tf:144-150, 234-254`). A `data "external"` check runs `aws s3api get-bucket-location` and fails fast on a cross-region bucket (`s3_endpoint.tf:111-130, 31-41`). The policy it writes (`aws-serverless-ncc/tf/s3_endpoint.tf:169-190`):

```hcl
  statement {
    sid    = "AllowDatabricksServerlessViaVpce"
    effect = "Allow"

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    actions = ["s3:*"]

    resources = [
      "arn:aws:s3:::${var.external_location_bucket_name}",
      "arn:aws:s3:::${var.external_location_bucket_name}/*"
    ]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceVpce"
      values   = [local.s3_vpc_endpoint_id]
    }
  }
```

This is an **Allow**, not a Deny. The README's claim that it makes "only the Databricks-owned VPC endpoint … reach the bucket" (`aws-serverless-ncc/README.md:11`) is therefore wrong: other access paths stay open. It also grants `s3:*` to any principal routed through that VPCE (see §8).

**Azure exfiltration control** (`workspace-setup/terraform-examples/azure/azure-privatelink-classic/tf/service_endpoint_policy.tf:19-41`):

```hcl
resource "azurerm_subnet_service_endpoint_storage_policy" "dp" {
  name                = "sep-${local.prefix}-dp"
  resource_group_name = local.dp_rg_name
  location            = local.dp_rg_location
  tags                = local.tags

  definition {
    name              = "databricks-managed"
    description       = "Databricks-managed storage: artifact Blob storage, system tables, log storage (DBFS root uses private endpoints)"
    service           = "Global"
    service_resources = ["/services/Azure/Databricks"]
  }

  dynamic "definition" {
    for_each = length(var.service_endpoint_policy_storage_accounts) > 0 ? [1] : []
    content {
      name              = "customer-storage"
      description       = "Additional customer-managed storage accounts (e.g. Unity Catalog external locations, data lake accounts)"
      service           = "Microsoft.Storage"
      service_resources = var.service_endpoint_policy_storage_accounts
    }
  }
}
```

A gotcha follows from this: any **new** UC storage account must be added to `service_endpoint_policy_storage_accounts` (`variables.tf:91-95`), or classic clusters get 403s on it. The Microsoft.Storage service endpoint on the subnets (`network.tf:122-123, 161-162`) routes storage traffic through the policy.

**GCP PSC DNS trick** (`workspace-setup/terraform-examples/gcp/gcp-byovpc-classic-psc/tf/dns.tf:18-21, 39-47`). The code extracts `8296020533331897.7` from the workspace URL and writes `<id>.gcp.databricks.com`, `dp-<id>…` and `tunnel.<region>…` A records into a private zone:

```hcl
locals {
  # Extracts e.g. "8296020533331897.7" from the workspace URL.
  workspace_id = regex("[0-9]+\\.[0-9]+", databricks_mws_workspaces.databricks_workspace.workspace_url)
}
resource "google_dns_record_set" "workspace_url" {
  count        = var.create_private_dns ? 1 : 0
  project      = var.google_project_name
  managed_zone = google_dns_managed_zone.databricks_private_zone[0].name
  name         = "${local.workspace_id}.${var.dns_name}"
  type         = "A"
  ttl          = 300
  rrdatas      = [google_compute_address.rest_api_ip.address]
}
```

**State and backends.** *No example declares a `backend`* (grep finds none). All state is local `terraform.tfstate`, and the `.gitignore` files exclude it (for example `aws-byovpc-uc/.gitignore:5-8`). Nothing provides state locking or encryption at rest. The only multi-environment advice is `terraform workspace new prod-1` with local state (`aws-serverless-ncc/README.md:202-215`). Provider pinning is inconsistent:

* `~> 1.84` in most scenarios;
* `>= 1.76.0` with no upper bound in `aws-serverless-ncc/tf/versions.tf:7`;
* `>=1.24.0` with google/random fully unpinned and no `required_version` in all three GCP `versions.tf`;
* exactly `1.130.0` in ABAC.

The azure-privatelink example commits `.terraform.lock.hcl` even though the root `.gitignore:7-8` says never to track it.

**Design decisions.**

* **Flat roots** make the examples teachable but copy-paste heavy: the IAM, bucket and metastore blocks are duplicated across four AWS scenarios.
* **Deprecated plus recommended pairs** are kept for existing users (`terraform-examples/README.md:72-80`).
* **Metastore without a storage root**, with managed storage set per catalog, follows the modern UC layout.
* **Sleeps for eventual consistency**: IAM 30/60 s, workspace 120 s, NCC-delete 30 s via `destroy_duration` (`aws-serverless-ncc/tf/ncc.tf:13-24`).
* **Preconditions and validations** encode customer mistakes (subnet count, metastore region match, CIDR size, XOR create-or-attach metastore at `azure-vnet-injection-uc/tf/databricks.tf:78-83`).

**Gotchas.**

* `force_destroy = true` is set on metastores, buckets, external locations and catalogs (for example `aws-byovpc-uc/tf/metastore.tf:12`, `unity_catalog.tf:85,113,122`). The **metastore is created in the same stack as a workspace**. A later `terraform destroy` of that stack deletes a region-wide metastore that other workspaces may now share.
* Nothing in the repo creates **cluster policies**, **customer-managed keys**, **grants on the new catalog**, audit-log delivery, IP access lists, front-end PrivateLink or workspace-catalog bindings. The only policy use is a *lookup* of the built-in Personal Compute policy (`azure-vnet-injection-uc/tf/cluster.tf:15-18`). `isolation_mode` is commented out (`aws-byovpc-uc/tf/unity_catalog.tf:123-124`).
* The workspace provider is configured from a resource attribute. Single-apply works, but it is the classic "provider depends on resource" fragility. The NCC example documents a provider v1.114+ plan-time bug around it (`aws-serverless-ncc/tf/s3_endpoint.tf:227-233`).

**How it scales.** One root is one workspace (plus possibly one metastore). To reach N workspaces you need four changes:

1. Split *account-level singletons* (metastore, NCC, groups) into their own state.
2. Wrap per-workspace roots in modules using `for_each`.
3. Use remote state with locking (S3 plus a DynamoDB or native lockfile, an azurerm blob lease, GCS, or TFC).
4. Enforce policies and tags centrally.

The README points to the SRA templates for that level of rigour (`terraform-examples/README.md:17-19`).

**What to learn.**

* The **order of operations**: identity, then network, then workspace, then metastore assignment, then UC credential, then external location, then catalog.
* **Account vs workspace provider scopes.**
* **Private connectivity differs by cloud**: AWS registers VPCEs and PAS, Azure uses a PE on the workspace resource plus private DNS, GCP uses PSC forwarding rules plus a private zone.
* **Serverless needs its own NCC path.** The customer's VPC does not cover serverless compute.

### 3.2 `data-governance/unity-catalog-abac`

**Purpose.** Stop maintaining masks and filters table by table. Let **Data Classification** tag PII (`class.email_address`, `class.age`, …) and let **ABAC policies** at catalog or schema scope match on tags (`README.md:1-5`).

**How it works.**

1. `demo/setup.sql:1-49` creates `abac_demo.user` (10 rows, 3 tenants) and three SQL UDFs: an RLS predicate and two constant masks.
2. Governed tag: `CREATE GOVERNED TAG abac_demo_rls … VALUES ('tenant')` (`README.md:138-142`), in Terraform as `databricks_tag_policy` (`demo/tf/governed_tags.tf:6-14`).
3. Tag assignment: `ALTER TABLE … ALTER COLUMN tenant_name SET TAGS ('abac_demo_rls'='tenant')` (`README.md:167-171`), in Terraform as `databricks_entity_tag_assignment` (`governed_tags.tf:16-44`). The demo *manually* assigns the system `class.*` tags because "the automatic Data Classification Terraform resource contains a bug" (`demo/tf/main.tf:1`, `demo/README.md:5-12`).
4. Policies: `CREATE POLICY … ON SCHEMA … COLUMN MASK fn TO \`account users\` FOR TABLES MATCH COLUMNS has_tag('class.email_address') AS c ON COLUMN c` (`README.md:218-248`). The Terraform equivalent is `databricks_policy_info` (`demo/tf/abac_policy.tf:1-76`).
5. Principals: account group `abac_demo_group_1`, the operator added to it, and workspace `USER` assignment (`demo/tf/groups.tf:4-25`).
6. Verification: `SHOW POLICIES`, `SHOW EFFECTIVE POLICIES`, `DESCRIBE POLICY` (`README.md:290-301`) and `system.information_schema.column_tags` (`README.md:84-106`).

Excerpt, the RLS predicate (`data-governance/unity-catalog-abac/demo/setup.sql:31-37`):

```sql
CREATE OR REPLACE FUNCTION filter_users_rls(tenant STRING)
RETURNS BOOLEAN
RETURN CASE
    WHEN tenant IS NULL THEN FALSE
    WHEN is_account_group_member('abac_demo_group_1') AND tenant = 'tenantB' THEN TRUE
    ELSE FALSE
END;
```

Excerpt, the tag-matched row-filter policy in Terraform (`data-governance/unity-catalog-abac/demo/tf/abac_policy.tf:1-28`):

```hcl
resource "databricks_policy_info" "tenant_row_isolation" {
  on_securable_type     = "SCHEMA"
  on_securable_fullname = "${var.catalog_name}.${var.schema_name}"
  name                  = "tenant_row_isolation"
  comment = "Restrict rows by tenant membership via the filter_users_rls function"

  policy_type           = "POLICY_TYPE_ROW_FILTER"
  for_securable_type    = "TABLE"
  to_principals         = ["account users"]
  except_principals     = []

  match_columns = [
    {
      condition = "has_tag_value('${databricks_tag_policy.tag_rls.tag_key}', 'tenant')"
      alias     = "rls_col"
    }
  ]

  row_filter = {
    function_name = "${var.catalog_name}.${var.schema_name}.filter_users_rls"
    using = [
      {
        alias = "rls_col"
      }
    ]
  }
  depends_on = [ databricks_tag_policy.tag_rls ]
}
```

**Design decisions.**

* Mask functions are *pure* (`RETURN '***@***'`, `setup.sql:40-49`). "Who is exempt" lives in the policy's `TO` and `EXCEPT` lists rather than in `is_member()` branches inside each function. That separates **what** from **who**.
* Exemptions are opt-in. The `Governance_Admins` `EXCEPT` clause is commented out, so admins are governed too (`README.md:274-282`).

**Gotchas.**

* First query returns **zero rows** by design (`README.md:311`). Account group membership propagation delays results.
* An Azure-only first-apply error ("Unknown tag policy key") is fixed by re-applying (`demo/README.md:216-218`).
* Terraform depends on out-of-band `setup.sql` and a CLI profile named `account` (`demo/tf/providers.tf:9-15`), which makes it unfit for CI as written.
* The troubleshooting advice to "Delete the state files" (`demo/README.md:204-206`) orphans governance objects.

**How it scales vs per-table grants and masks.** Per-table RLS and masks cost O(tables × rules) DDL, and each new table is ungoverned until someone remembers. ABAC costs O(policies). Governance attaches automatically when a column receives a tag, and Data Classification makes tagging itself automatic (`README.md:332-352`). The remaining scale limits are:

* tag hygiene (governed-tag `ASSIGN` permission, allowed values);
* per-row predicate cost: prefer SQL UDFs and mapping-table joins over hard-coded `CASE` branches; the demo's `CASE` mapping (`setup.sql:33-37`) does not scale to many tenants;
* policy-count and quota limits (which the README defers to docs, `README.md:18`).

### 3.3 `data-warehousing/pbi-aibi-converter`

**Purpose.** Convert a Power BI **.pbip** (zipped) or **.pbit** into a published AI/BI dashboard from a self-service Databricks App (`README.md:1-39`).

**Pipeline, traced from `app_for_conversions/app.py:263-541`.**

1. **Warehouse.** It uses `DATABRICKS_WAREHOUSE_ID`, falling back to the *first* warehouse the app's SP can list (`app.py:277-292`).
2. **Extract.** `extract_upload` writes the upload and runs `zipfile.extractall`. For a `.pbit` it decodes the UTF-16 TMSL `DataModelSchema` and **synthesizes** TMDL files (tables, measures, partitions, relationships). It explodes the legacy monolithic `Report/Layout` into PBIR `pages/*/visuals/*/visual.json` (`converter.py:113-138, 341-542`).
3. **Parse.** `collect_pbi_context` concatenates slimmed TMDL (lineage tags and annotations dropped) and slimmed visual JSON (formatting dropped) into one text prompt (`converter.py:954-1085`). `extract_pbi_source_tables` regex-parses M navigation steps `[Name="x",Kind="Database|Schema|Table"]` into `catalog.schema.table` (`converter.py:589-663`). `detect_external_sources` classifies connectors: `DatabricksMultiCloud`/`Databricks.Catalogs` count as Databricks, Sql.Database, Snowflake and others do not (`converter.py:667-757`). Non-Databricks sources are only **warned about** (`app.py:320-324`).
4. **Layout, deterministically.** Pixels on a 1280×720 canvas map to a 6-column grid (x and width scaled by 6/1280, height by 12/720, minimum 2 rows). Visuals are then packed by *column-skyline* (`converter.py:1287-1515`). A slicer present on **every** page becomes a global filter (`converter.py:1220-1250`). The app **always** uses the "free layout" blueprint, which lists the visuals and lets the LLM place them (`app.py:341`). The stricter blueprint and `apply_blueprint_positions` exist but are dead code: they are not imported (`app.py:25-45`).
5. **LLM.** The system prompt is ~72 KB of four knowledge docs plus critical reminders (`converter.py:32-101`). The model is an OpenAI-compatible Model Serving endpoint called at `temperature=0` (`converter.py:2279-2284`). Output-truncation recovery: if `finish_reason=="length"` *or* braces are unbalanced, the code appends "Continue EXACTLY where you left off", up to 12 rounds (`converter.py:2211-2303`). Above an estimated 190k tokens (`len/4`), pages are sent in batches in a growing multi-turn chat (`converter.py:2365-2482`).
6. **Deterministic repair (the AI-stewardship layer).**
   * `extract_json_from_response` strips code fences.
   * `_promote_aggregations_to_custom_calcs` moves `SUM/AVG/COUNT/MIN/MAX` out of GROUP BY dataset SQL into widget expressions (`converter.py:2606-2762`).
   * `_sanitize_widget_columns` drops fields that reference non-existent columns (`converter.py:2765-2848`).
   * `_ensure_fqn_tables` prefixes one- and two-part names with the most common catalog and schema (`converter.py:2851-2922`).
   * `fix_dataset_columns` **executes** each dataset as `SELECT * FROM (<sql>) _t LIMIT 0`. On `UNRESOLVED_COLUMN` it runs `DESCRIBE TABLE` and fuzzy-replaces the column, up to 5 attempts (`converter.py:2925-3098`).
7. **Colors.** PBI theme and data colors are injected into `scale.range`/`mappings`. Categorical pies query `SELECT DISTINCT` through a safe-identifier guard (`color_utils.py:40-103`).
8. **Validate, report only.** Structural checks (widget versions, fieldName↔fields, dataset references), SQL `LIMIT 1` execution, layout fidelity and table coverage (`validator.py:148-555`). Results are displayed but **do not gate** deployment (`app.py:422-509`).
9. **Deploy.** `lakeview.create` into `/Workspace/Shared/aibi_converter/<name>` (`app.py:440-452`), grant the requesting user `CAN_MANAGE` using the `X-Forwarded-Email` header (`app.py:198-260`), then `lakeview.publish` (`app.py:507-509`), a second LLM call for a markdown "conversion report", and a PDF.

Excerpt, the safety wrapper used to test LLM SQL (`data-warehousing/pbi-aibi-converter/app_for_conversions/converter.py:2944-2956`):

```python
    def _run_query(sql: str) -> tuple[bool, str]:
        try:
            stmt = sp_client.statement_execution.execute_statement(
                warehouse_id=warehouse_id,
                statement=f"SELECT * FROM ({sql}) AS _t LIMIT 0",
                wait_timeout="30s",
            )
            if stmt.status and stmt.status.state == StatementState.SUCCEEDED:
                return True, ""
            error_msg = stmt.status.error.message if stmt.status and stmt.status.error else "Unknown"
            return False, error_msg
        except Exception as e:
            return False, str(e)
```

Excerpt, the aggregation "promotion" rewrite (`converter.py:2703-2719`):

```python
        tree.args["expressions"] = non_agg_selects
        tree.args.pop("group", None)
        tree.args.pop("having", None)

        order = tree.args.get("order")
        if order:
            agg_alias_set = set(agg_aliases)
            kept = [
                o for o in order.expressions
                if not any(c.name in agg_alias_set for c in o.find_all(E.Column))
            ]
            if kept:
                order.args["expressions"] = kept
            else:
                tree.args.pop("order")

        ds["query"] = tree.sql(dialect="spark", pretty=True)
        dataset_agg_map[ds_name] = agg_aliases
```

I reproduced this rewrite with `sqlglot 26.33`. The input was a top-N query:

```sql
SELECT p.product, SUM(s.revenue) AS revenue … GROUP BY p.product HAVING SUM(s.revenue) > 1000 ORDER BY revenue DESC LIMIT 10
```

It became:

```sql
SELECT p.product, s.`revenue` FROM … JOIN … LIMIT 10
```

with the widget doing `SUM(\`revenue\`)`. The HAVING and ORDER BY are gone, and the LIMIT now applies to raw joined rows: the result is silently wrong numbers.

**What maps cleanly vs not.**

* **Maps cleanly:**
  * `card`→`counter`, line/bar/column→`line`/`bar`, donut/pie→`pie`, `pivotTable`→`table` (`README.md:157-167`);
  * dropdown or date slicers→filter widgets;
  * simple aggregations (`README.md:171-177`);
  * theme colors;
  * page count.
* **Does not map:**
  * DAX **filter context**: CALCULATE overrides, REMOVEFILTERS/ALL/ALLEXCEPT, time intelligence (see §6);
  * maps and custom visuals, via fallbacks (`knowledge/VISUAL_ALTERNATIVES_GUIDE.md:24-68`);
  * **PBI RLS roles**: the parser never reads `definition/roles` or TMSL `model.roles` (`converter.py:1018-1042, 518-542`), so they are silently dropped;
  * Power Query (M) transformations beyond source navigation;
  * data that is not already in Databricks.

**How DAX→SQL is handled.** It is not compiled. The LLM is given a pattern cookbook (`knowledge/DAX_TO_SQL_GUIDE.md`, 17 sections: DIVIDE→`NULLIF`, CALCULATE→`SUM(CASE WHEN …)`, SAMEPERIODLASTYEAR→self-join or `LAG`, TOTALYTD→window, calculated tables→CTEs). Correctness is then checked only for *executability* (the SQL runs and the columns exist), not for *numeric equivalence*. Several cookbook entries are semantically wrong (§8 R55), and the knowledge docs contradict each other (§8 R54).

**Scale.** The app converts one report per LLM call. It processes up to 10 uploads *sequentially* in one Streamlit session (`app.py:925-927`). Each dataset costs up to 5 statement executions plus DESCRIBEs. Tokens are estimated as `len/4` (`converter.py:2180-2182`). An estate of hundreds or thousands of reports needs:

* a job or queue;
* dedup of shared semantic models, ideally converted once into **metric views**;
* reconciliation tests against PBI outputs;
* human review queues.

### 3.4 `data-warehousing/dbrx-business-semantics`

**Purpose.** Define KPIs once as **UC metric views** (YAML 1.1) and reuse them in AI/BI, Genie and SQL clients (`README.md:5-7, 93-100`).

**How it works.**

* `0_IngestData.ipynb` downloads a Kaggle star schema into a UC volume with `kagglehub` and writes Delta tables using `inferSchema=True`, then `DROP TABLE` + `saveAsTable` (`0_IngestData.ipynb:137-183`).
* `1_CreateMetricView.ipynb:89-507` runs `CREATE OR REPLACE VIEW … WITH METRICS LANGUAGE YAML`. The YAML contains:
  * **star and snowflake joins** (`dim_campaigns → campaign_start_date/end_date`, `dim_stores → store_manager_salesperson`, `:95-137`);
  * dimensions with `display_name`, `synonyms` and `format`;
  * 11 aggregate measures;
  * **window measures** with `semiadditive: last` (previous/current day, running total, YTD, trailing 7- and 30-day distinct customers, `:445-507`).
* `2_QueryMetricView.ipynb` queries with `MEASURE()` and `GROUP BY ALL`. It creates a Genie space by POSTing `serialized_space` using the notebook's internal API token (`2_QueryMetricView.ipynb:182-192`), and templatizes the dashboard JSON.
* `3_MaterializeMetricView.ipynb:504-513` adds `materialization: {schedule: every 10 hours, mode: relaxed, materialized_views: [unaggregated baseline, aggregated by dayOfWeek]}`. You verify it with `EXPLAIN EXTENDED` (look for `__materialization_mat`).

Excerpt (window measures, `1_CreateMetricView.ipynb:463-487`, YAML inside the notebook cell):

```yaml
  - name: day_over_day_growth
    expr: (MEASURE(current_day_sales) - MEASURE(previous_day_sales)) / MEASURE(previous_day_sales) * 100

  - name: running_total_sales
    expr: SUM(total_amount)
    comment: Running Total Sales
    display_name: Running Total Sales
    synonyms: ['running sales']
    window:
      - order: sales_date
        range: cumulative
        semiadditive: last

  - name: ytd_sales
    expr: SUM(total_amount)
    comment: YTD Sales
    display_name: YTD Sales
    synonyms: ['year-to-date sales']
    window:
      - order: sales_date
        range: cumulative
        semiadditive: last
      - order: year
        range: current
        semiadditive: last
```

**Gotchas.**

* The shipped Genie examples call measures that don't exist (`total_sales`, `pct_of_relevance_of_sales`, `genie_space.json:257-258, 290`). One aliases the **median** as "pct_of_relevance" (`:302-305`), which teaches Genie wrong semantics.
* The dashboard sums the `total_amount` **dimension** instead of calling `MEASURE(sales_sum)` (`dashboard_and_genie/dashboard.lvdash.json:29,80`), bypassing the semantic layer.
* Calendar `year` and `month` carry "fiscal" synonyms (`1_CreateMetricView.ipynb:249,254`).
* Customer email is exposed as a Genie dimension with a value dictionary (`:171`; `genie_space.json` `build_value_dictionary`).
* The 300-line YAML is duplicated between notebooks 1 and 3.

**Scale.** Metric views compute at query time over the declared joins. Cost grows with fact size, join fan-out and window measures. Materialization (experimental) precomputes chosen grains on a schedule. Because governance is UC-native, masks and filters on base tables follow the metric view (inferred from UC semantics).

### 3.5 `data-engineering/lakeflow-connect`

**SQL Server CDC bundle.** A **UC connection** (credentials hidden behind `USE CONNECTION`, and secrets preferred over literals, `sql-server-cdc/README.md:55-87`) feeds two pipelines:

* an **ingestion gateway** that stages snapshot and CDC data in a UC volume, on classic compute (`resources/ingestion_gateway.pipeline.yml:1-10`);
* an **ingestion pipeline** that applies changes into streaming tables. It references the gateway through `${resources.pipelines.ingestion_gateway.id}` (`resources/ingestion_pipeline.pipeline.yml:6`), and `objects` lists tables or whole schemas with optional `table_configuration` (primary keys, `sequence_by`, include/exclude columns).

A daily periodic job refreshes the pipeline (`resources/trigger_ingestion.job.yml:8-21`); the schedule is paused in dev mode. Only a `dev` target exists, and `prod` is commented out (`databricks.yml:9-19`). A `RUNBOOK.md` is written *for an AI coding agent*: explicit PAUSE points, "do not invent credentials", and a progress tracker (`RUNBOOK.md:1-43`).

Excerpt (`data-engineering/lakeflow-connect/sql-server-cdc/resources/ingestion_gateway.pipeline.yml:1-10`):

```yaml
resources:
  pipelines:
    ingestion_gateway:
      name: ${var.ingestion_gateway_name}
      gateway_definition:
        connection_name: ${var.connection_name}
        gateway_storage_catalog: ${var.staging_catalog}
        gateway_storage_schema: ${var.staging_schema}
        gateway_storage_name: ${var.ingestion_gateway_name}
      clusters: ${var.gateway_cluster}
```

**Discrepancy with the official docs.** The Lakeflow Connect docs' bundle example sets `continuous: true` with the comment "Gateway pipelines must be continuous". They warn that a stopped gateway can lose changes once the source log truncates, forcing a full refresh. This bundle omits `continuous`, and the RUNBOOK waits for the gateway run to reach "COMPLETED / SUCCESS" (`RUNBOOK.md:124-132`), which treats it as a batch. The default node types are Azure-only (`variables.yml:41-47`).

**Connectivity validator notebook.**

* Four steps: DNS, then TCP (distinguishing timeout vs refused vs unreachable), then TLS (explicitly "informational", because SQL Server, PG and MySQL negotiate TLS *inside* the protocol), then an optional app probe (`README.md:13-26`).
* The SQL Server probe is a **hand-written TDS PRELOGIN/LOGIN7 client** that tunnels TLS through MemoryBIO (`lakeflow-cdc-source-validator.ipynb:685-958`).
* Secrets come from UC secrets or a legacy scope.
* It reports the egress IP (via `checkip.amazonaws.com` or `ifconfig.me`, `ipynb:1230-1239`), region match and path type, and prints an `aws ec2 authorize-security-group-ingress` snippet.
* Gotcha: the gateway runs on classic compute in the customer network. Run the notebook on *classic* compute in that network, not serverless, to test the gateway's real path. Serverless egress IPs rotate (`lakeflow-cdc-source-validator.ipynb:539`).

**Scale.** One gateway per source database runs continuously on classic compute, and ingestion runs on serverless. The limits are the source CDC log retention versus gateway uptime, the table count per pipeline, and gateway cluster sizing (ENHANCED autoscale, 1–5 workers here).

### 3.6 `data-engineering/sdp-evolution`

**Purpose.** Survive schema drift (rename, type change, new column) **without a full refresh** (`README.md:9-17`).

**How it works.** Bronze uses Auto Loader with a **fixed schema**, `schemaEvolutionMode=rescue` and `rescuedDataColumn=_rescued_data` (`src/pipeline.py:16-28`). Silver is a materialized view that in STATE 1 passes the v1 columns through. The demo toggles to STATE 2, `reconcile(df)`, by *editing code* (`src/pipeline.py:31-59`).

`reconcile` parses `_rescued_data` with `from_json` and `coalesce`s each business column (`src/reconcile.py:17-28`):

```python
RESCUE_SCHEMA = "customer_name string, amount double, loyalty_tier string"


def reconcile(df: DataFrame) -> DataFrame:
    r = F.from_json(F.col("_rescued_data"), RESCUE_SCHEMA)
    return df.select(
        "order_id",
        F.coalesce(F.col("cust_name"), r["customer_name"]).alias("customer_name"),
        F.coalesce(F.col("amount").cast("double"), r["amount"]).alias("amount"),
        r["loyalty_tier"].alias("loyalty_tier"),
        "order_ts",
    )
```

**Bundle.** It declares a UC schema and managed volume as bundle resources (`resources/uc.yml:1-14`), seed jobs on serverless (`resources/seed_jobs.yml`), and a notebook unit-test job whose success is the test gate (`resources/test_job.yml`, `tests/test_reconcile_notebook.py:23-48`). It uses `pyspark.pipelines` on `channel: PREVIEW` (`resources/pipeline.yml:8`) and `experimental.skip_name_prefix_for_schema` (`databricks.yml:4-5`).

**Gotcha, reproduced.** Spark's JSON reader coerces a JSON *number* into a STRING column. With OSS Spark 4.0.1, `{"amount": 88.40}` read with `amount string` yields `"88.40"`, not null. So the v2 `amount` is probably *not* rescued, contrary to `README.md:188`. Only the rename and the new column land in `_rescued_data`. The final result is still correct because `coalesce` prefers the base column. (The Databricks rescue semantics were not verified.)

**Scale.** One small reconcile mapping per silver table. Materialized-view recompute cost can be full rather than incremental for non-deterministic or complex plans (inferred). Parsing `_rescued_data` JSON costs CPU on every refresh.

### 3.7 `core-platform/cicd`

**Customer 360 Lakehouse + Genie.** One bundle declares:

* a schema and volume;
* an SDP pipeline: Python bronze with Auto Loader and expectations (`src/pipeline/01_bronze.py:23-47`), then SQL silver and gold materialized views (`02_silver.sql`, `03_gold.sql`);
* a metric view created by a notebook task, because metric views have no PySpark API (`src/metric_view/mv_customer_health.py:21-68`);
* a dashboard whose bare table names are rebound per target by `dataset_catalog`/`dataset_schema` (`resources/customer360_dashboard.dashboard.yml:12-13`);
* a native **`genie_spaces`** resource that requires `engine: direct` (`databricks.yml:21-23`, `resources/customer360_genie.genie_space.yml`);
* a setup job wiring data generation, the pipeline, the metric view and validation (`resources/customer360_setup.job.yml:16-47`).

The isolation model is **per-workspace**: the same catalog and schema names in separate dev and prod workspaces (`databricks.yml:49-54`). Prod pins the root path and `run_as` to an SP (`databricks.yml:66-71`):

```yaml
  prod:
    mode: production
    workspace:
      root_path: /Workspace/Shared/.bundle/${bundle.name}/prod
    run_as:
      service_principal_name: ${var.prod_service_principal}
```

The **3-phase deploy** exists because the Genie resource validates that its tables exist at *deploy* time, while the job creates them at *run* time (`README.md:66-93`). In GitHub Actions (`.github/workflows/deploy.yml:52-57`):

```yaml
      - name: Phase 1 — deploy all except Genie (dev)
        run: databricks bundle deploy -t dev --var warehouse_id=${{ secrets.DEV_WAREHOUSE_ID }} --select schemas.customer360_schema,volumes.raw_data,pipelines.customer360_pipeline,dashboards.customer360_dashboard,jobs.customer360_setup
      - name: Phase 2 — run setup job to build tables (dev)
        run: databricks bundle run -t dev customer360_setup --var warehouse_id=${{ secrets.DEV_WAREHOUSE_ID }}
      - name: Phase 3 — full deploy incl. Genie (dev)
        run: databricks bundle deploy -t dev --var warehouse_id=${{ secrets.DEV_WAREHOUSE_ID }}
```

**Branch strategy (identical across four CI systems).**

1. A feature-branch push validates and deploys to the dev workspace.
2. A PR to main validates only.
3. A push to main deploys to prod as the SP, using OAuth M2M (`DATABRICKS_HOST`, `DATABRICKS_CLIENT_ID`, `DATABRICKS_CLIENT_SECRET`) and one SP per environment (`AGENTS.md:89-138`).

The pipelines differ in form: Azure DevOps is a single job with conditions and explicit secret→env mapping (`azure-pipelines.yml:40-74`), GitLab uses the CLI container (`.gitlab-ci.yml:21`), and Jenkins is multibranch with `withCredentials` (`Jenkinsfile:19-86`).

**Analytic caveats.**

* "At risk" is the generator's planted `is_cohort` flag, not the computed score (`03_gold.sql:44-45`, `generate_data.py:136`).
* Snapshot measures (`account_count`, `arr_total`) are **summed across a daily spine** (`mv_customer_health.py:40-43` over `03_gold.sql:52-94`). They overstate totals for any multi-day slice, which is exactly the case semi-additive windows exist for (see §3.4).

**dabs-migrator (an agent skill).** Given `job:foo pipeline:bar …`, the agent reads live assets through the CLI and emits the following (`dabs-migrator/SKILL.md:56-68`):

* `databricks.yml` from a template (dev, staging and prod targets; `run_as` SP variables);
* one YAML per resource, mapped against a pinned `databricks bundle schema` dump (`dabs-schema.json`);
* a verbatim copy of the source;
* CI files for one of six tools;
* test stubs.

It also has an incremental mode that refuses to overwrite existing files. Its **Hard rules** and **CHANGELOG** read like a field log of AI failure modes:

* read-path failures: stderr corrupting `jq`, and `genie get-space` omitting `serialized_space` (`CHANGELOG.md:9-26`);
* validate-time failures: undeclared variables (`:51-61`);
* deploy-time failures that pass `validate`: an empty `notification {}`, dashboards rebuilt from API paths, Genie IDs like `q1` (`:30-47`);
* "validates but wrong" failures: a paused alert re-activated, IDs hard-coded (`:59-63`).

Rule of thumb (`SKILL.md:134`): *"Validation is necessary but not sufficient — a bundle isn't 'done' until it deploys."* The generated GitHub Actions flow is PR validate, then staging on push to main, then prod on a `v*` tag with `environment: prod` approvals (`cicd/github-actions.md:17-135`). The target is selected by `DATABRICKS_BUNDLE_ENV`, never `-t` (`SKILL.md:102-112`). A repo workflow zips the skill and cuts a release on every change (`.github/workflows/release.yml:1-41`).

**OrderFlow (Apps + Lakebase).**

* Lakebase is declared as bundle resources: `postgres_projects`, `postgres_branches`, `postgres_endpoints`, `postgres_databases`, `postgres_roles` (`resources/lakebase.yml:5-39`).
* The app attaches the DB as an **app resource** with `CAN_CONNECT_AND_CREATE`, which auto-injects `PGHOST`, `PGUSER`, `PGPORT` and `PGDATABASE` (`resources/app.yml:13-19`).
* The FastAPI pool mints an **OAuth DB token per new connection** and recycles connections at 45 min, before the 1 h token expiry (`app/server/db.py:17-50`).
* A job copies Lakebase tables into UC bronze with psycopg (`jobs/ingest_lakebase.py:25-50`), runs an SDP medallion (`pipeline/transformations.py`), and appends a daily snapshot plus a CSV export (`jobs/daily_rollup.py:27-42`).
* Prod adds explicit bundle **permissions** and a job-scoped `run_as`, because "apps must run as their owner, so a bundle-level run_as would fail" (`databricks.yml:69-83`).

Excerpt (`core-platform/cicd/orderflow-app-lakebase/app/server/db.py:17-24, 43-50`):

```python
class OAuthConnection(psycopg.Connection):
    """Mints a fresh Lakebase OAuth token for every new connection."""

    @classmethod
    def connect(cls, conninfo="", **kwargs):
        cred = _w.postgres.generate_database_credential(endpoint=_ENDPOINT_NAME)
        kwargs["password"] = cred.token
        return super().connect(conninfo, **kwargs)
pool = ConnectionPool(
    conninfo=f"dbname={_database} user={_pg_user()} host={_host} port={_port} sslmode={_sslmode}",
    connection_class=OAuthConnection,
    min_size=1,
    max_size=10,
    max_lifetime=2700,  # recycle before the 1-hour OAuth token expires
    open=False,          # opened in FastAPI lifespan
)
```

**Build is broken from a clean clone (reproduced).** The root `.gitignore:1` pattern `*conf*.json` matches `tsconfig.json`; `git check-ignore -v` confirms it. The frontend therefore ships without tsconfig files, while `npm run build` is `tsc -b && vite build` (`app/frontend/package.json:8`). Running `tsc -b` without a tsconfig fails with `TS5083: Cannot read file …/tsconfig.json`, so the build steps in `ci.yml:34-38` and `deploy.yml:32-36` fail.

### 3.8 `workspace-setup/aim-user-ownership-inventory`

**Purpose.** AIM (Automatic Identity Management) matches identities to Entra by Object ID. Its prep script flags divergent users, often ex-employees. Deleting a user deletes `/Users/<email>/`, breaks jobs whose `run_as` is that user, and invalidates their PATs (`README.md:16-34`).

**How it works.**

* It resolves numeric IDs or emails through SCIM. Unresolved inputs are listed rather than dropped, and unknown emails are still scanned because creator fields persist (`user_owned_objects_inventory.py:122-161`).
* Each scan section is wrapped in `@safe`, so one API failure doesn't abort the run (`:215-227`).
* It scans:
  * jobs (creator and `settings.run_as`), clusters (creator and single user), cluster policies, warehouses, pipelines (creator), DBSQL queries and alerts (owner), PATs;
  * Lakeview dashboards, experiments and legacy models through the Permissions API (direct, non-inherited `IS_OWNER` or `CAN_MANAGE`, `:189-212`);
  * UC registered models (owner), Repos (path);
  * a recursive walk of each home folder (`:229-444`).
* Output is a DataFrame plus CSV, optionally copied to a UC volume (`:453-501`), with a list of "users with NO workspace objects found" (`:469-475`).
* It is report-only and workspace-scoped. UC ownership is explicitly out of scope; use `ALTER … OWNER TO` separately (`README.md:64-82`).

Excerpt, the resilience decorator (`workspace-setup/aim-user-ownership-inventory/user_owned_objects_inventory.py:215-227`):

```python
def safe(section):
    """Decorator: wrap a scan section so that calling it runs with error handling —
    one failing API won't abort the whole inventory. Returns a callable (does NOT run
    the scan at decoration time)."""
    def deco(fn):
        def wrapped():
            try:
                fn()
                print(f"  [ok] {section}")
            except Exception as e:
                print(f"  [skip] {section}: {type(e).__name__}: {e}")
        return wrapped
    return deco
```

**Why ownership matters.**

* A job without explicit `run_as` runs as its **owner**.
* Many objects have exactly one owner, and ownership confers full control, including granting.
* Human owners leave; groups and SPs don't.

The OrderFlow Lakebase DB is owned by a human role (`orderflow-app-lakebase/resources/lakebase.yml:29-39`), which is exactly the pattern this notebook cleans up after.

**Scale.** It makes sequential REST calls and an N+1 permissions call per dashboard, experiment and model (`:338-383`). It runs once per workspace. At large scale, parallelize with a thread pool and persist results into a Delta table.

### 3.9 Smaller projects

**Pulumi `azure-hybrid`** (`__main__.py:1-55`). One resource group plus one workspace with `enableNoPublicIp` and `compute_mode="Hybrid"`, using `pulumi login --local` (local state, `README.md:37`). The `pulumi-azuread` dependency is unused (`requirements.txt:3`).

**PowerShell managed-VNet → VNet-injection.**

* `update_databricks_vnet.ps1` does five things:
  1. parses resource IDs;
  2. checks VNet subscription and region match, subnet delegation and NSG presence (`:144-343`);
  3. refuses to continue if managed-VNet peerings exist (`:126-142`);
  4. exports the workspace ARM template, removes legacy parameters, sets `apiVersion 2026-01-01` and injects `customVirtualNetworkId`/`custom*SubnetName` (`:392-447`);
  5. redeploys incrementally (`:499-504`).
* Microsoft documents that Terraform isn't supported for this path (`README.md:99`).
* `create_databricks_vnet.ps1` builds delegated subnets and NSGs but **no NAT** (`:183-233`).

**S3 Policy Migration.** Lists UC external locations, parses `s3://bucket/...` into bucket ARNs, and outputs the ARNs "requiring policy update" (`modules/workspace_credentials/main.tf:1-38`, `main.tf:44-47`). The *reason* for the migration is not stated (inferred: a Databricks-side change to bucket-policy requirements).

---

## 4. Platform-architecture lessons: the implied reference architecture

Read together, the examples imply the following target state. Items marked † are **absent** from the repo and must be added.

```
                    ┌────────────────────────── Databricks ACCOUNT (account console / account API) ───────────────────────────┐
  IdP (Entra/Okta) ─┼─SCIM / AIM─► users · groups · service principals ── mws_permission_assignment ──► workspaces (dev|stg|prod)│
                    │  Metastore (1 per region, OWNER = admins GROUP, no root storage)  ── metastore_assignment ──►  (all ws)   │
                    │  NCC (serverless egress) ── private-endpoint rules ─► S3 / ADLS / DBFS / RDS   (bucket policy: SourceVpce)│
                    │  Network cfg + VPC-endpoint registrations (REST, SCC relay) + Private Access Settings                     │
                    │  † budget/cluster policies · † audit-log delivery · † CMK · † IP access lists · † front-end PL            │
                    └───────────────────────────────────────────────────────────────────────────────────────────────────────────┘
  CUSTOMER CLOUD (per workspace)                                          UC STORAGE (per domain/catalog)
  ┌───────────────────────────── VPC / VNet (BYO) ─────────────────────┐   ┌───────────────────────────────────────────────┐
  │ compute subnets ×2+ AZ (Azure: delegated host+container, NPIP)      │   │ bucket / ADLS container (block public, TLS1.2)│
  │   └─ SCC relay & REST ──► PL/PSC endpoints (own subnet, own SG) ───┼──►│   ▲ storage credential: IAM role + external ID│
  │ egress: NAT | none(fully private) + SG/NSG allow-list               │   │   │   (self-assuming) | access connector MI    │
  │   + S3 gateway / service endpoints + Service-Endpoint Policy (Az)   │   │ external location ─► catalog.storage_root      │
  │ private DNS zones (privatelink.azuredatabricks.net, gcp.databricks) │   │ grants → GROUPS; owners → groups/SPs           │
  └─────────────────────────────────────────────────────────────────────┘   └───────────────────────────────────────────────┘
  GOVERNANCE: governed tags ◄─ Data Classification ─► ABAC policies (catalog/schema; TO/EXCEPT groups) ─► row filters · masks
  SEMANTICS : metric views (UC) ─► AI/BI dashboards (viewer vs EMBEDDED creds!) · Genie spaces (instructions, examples)
  DELIVERY  : Git ─PR─► bundle validate ─► deploy staging (SP) ─approval─► deploy prod (SP; run_as SP; permissions block)
              IaC state: remote backend + locking†;  account-level singletons in their own state†
```

**Identity.**

* Use OAuth M2M **service principals** for automation everywhere (`aws-byovpc-uc/tf/providers.tf:16-27`, `customer-360 AGENTS.md:106-113`). PATs appear only as a legacy aside.
* Grant workspace access through **identity federation** (`databricks_mws_permission_assignment`), not workspace-local users. The GCP examples still do the latter (`gcp-byovpc-standalone/databricks.tf:44-54`).
* Give governance roles to **groups** (the metastore owner group at `azure-vnet-injection-uc/tf/databricks.tf:44-71`).

**Networking.** Use BYO network with SCC/NPIP. Add back-end PrivateLink or PSC for control-plane traffic and restrict egress:

* AWS: SG egress to the VPC CIDR plus the S3 prefix list (`aws-byovpc-classic-privatelink/tf/network.tf:103-135`).
* Azure: service-endpoint policy plus the DBFS firewall (`azure-privatelink-classic/tf/service_endpoint_policy.tf:19-41`, `databricks.tf:38-39`).

Treat **serverless as a separate network plane**, governed by an NCC (`aws-serverless-ncc`, `azure-privatelink-classic/tf/ncc.tf`).

**UC hierarchy.** Metastore, then catalog, then schema, then tables, volumes, functions, models and metric views. Keep **one metastore per region**. Give catalogs **their own managed storage** through external locations and put isolation at the catalog/storage boundary. Credentials are UC securables, and `CREATE EXTERNAL LOCATION` and friends are metastore privileges (`aws-serverless-ncc/tf/metastore.tf:85-110`).

**Storage.** Use Databricks-generated IAM policies and trust policies (the data sources) rather than hand-written JSON. Keep versioning, public-access blocks and encryption explicit. Use `force_destroy` only in sandboxes.

**Compute policies.** Bind clusters to a policy (`azure-vnet-injection-uc/tf/cluster.tf:25-44`). The repo never authors one, so add policies for node types, auto-termination, tags and access mode.

**CI/CD.** Use one bundle per product. Keep dev in development mode (user-prefixed); staging and prod use production mode with `root_path` in `/Shared`, `run_as` an SP, and an explicit `permissions` block (`orderflow databricks.yml:53-83`, `dabs-migrator templates/databricks.yml.tmpl:40-61`). PRs validate only. Prod goes through approval (`dabs-migrator cicd/github-actions.md:89-127`), and nobody deploys prod from a laptop (`SKILL.md:124`).

---

## 5. Governance lessons

**Securable hierarchy and privileges.**

* Access needs the *path* privileges (`USE CATALOG`, `USE SCHEMA`) plus the object privilege (`SELECT`, `MODIFY`, `READ FILES`, …).
* Grants inherit downward.
* `databricks_grants` (plural) is **authoritative** for a securable and will revoke anything not listed. The NCC example has to order it after external-location creation, or it strips the SP's implicit privileges (`aws-serverless-ncc/tf/credential.tf:78-95`). `databricks_grant` (singular) is additive.
* New catalogs created by these templates have **no grants at all** (`aws-byovpc-uc/tf/unity_catalog.tf:116-128`), so only the deploying SP can use them until someone grants access.

**RBAC vs ABAC.**

* RBAC means grants on objects to groups. Row filters and column masks are attached per table (`ALTER TABLE … SET ROW FILTER fn ON (col)`, `ALTER COLUMN … SET MASK fn`).
* ABAC moves both into **policies bound to tags** at catalog or schema scope, with `TO`/`EXCEPT` principals, so new tables inherit governance once tagged (`unity-catalog-abac/README.md:210-352`).
* ABAC's prerequisites are:
  * governed tags, which are account-level with allowed values and need `ASSIGN` permission (`README.md:111-185`);
  * DBR 16.4+ or serverless (`README.md:14`);
  * a strategy for exemptions. Admins are *not* exempt by default (`README.md:282`).

**Row filter and mask functions.**

* Keep them pure and deterministic.
* Put identity checks in the policy, or in `is_account_group_member()` when you must.
* Drive tenant mapping from a table, not `CASE` literals (`setup.sql:31-37`).

**Ownership.**

* Owners have full control and job run-as defaults to the owner.
* Keep human owners out of production objects. The OrderFlow DB owner role is a person (`lakebase.yml:29-39`).
* Inventory ownership before identity changes (`aim-user-ownership-inventory`).

**Downstream governance traps.**

* **Published dashboards embed credentials by default.** The Lakeview publish API documents `embed_credentials` "Default: true". The PBI converter publishes without setting it (`app.py:507-509`), so every viewer's query runs as the app SP. Viewer-aware row filters and masks therefore evaluate for the SP, not the viewer.
* **Genie value dictionaries on PII columns** (`genie_space.json`, `customer_email`) copy sensitive values into Genie's index (inferred).
* **Semantic synonyms are governance-relevant.** A "fiscal year" synonym on a calendar year (`1_CreateMetricView.ipynb:249`) produces confidently wrong answers.

---

## 6. Migration lessons

**DW migration.** The `dw-migration/` track is empty (`dw-migration/README.md:1-7`). The repo nevertheless contains the building blocks:

* ingestion of legacy OLTP and DW sources through **Lakeflow Connect CDC**, with a network pre-flight first;
* **schema-drift tolerance** at bronze (`sdp-evolution`);
* rebuilding the **semantic layer as metric views**, so BI and Genie share definitions;
* moving UI-built assets **into code** (`dabs-migrator`).

What makes it hard: source network reachability, CDC log retention, type and precision mapping (see OrderFlow's `str(v)` ingestion, `ingest_lakebase.py:42`), and cutover reconciliation.

**PBI → AI/BI.**

1. **Data first.** The converter assumes tables are already in UC through the Databricks connector. Other connectors only trigger warnings (`app.py:320-324`).
2. **Layout is solvable deterministically.** Pixel→grid scaling plus skyline packing (`converter.py:1287-1515`) works.
3. **Semantics are the hard part.** DAX evaluates in a *filter context*: `CALCULATE` *overrides* slicer filters on the same column, while a SQL `SUM(CASE WHEN region='NA' …)` *intersects* with them. `REMOVEFILTERS`, `ALL` and time intelligence depend on context that SQL datasets do not model. The cookbook's `SUM(amount)/NULLIF(SUM(grand_total),0)` with a per-row `grand_total` window is off by the row count (`DAX_TO_SQL_GUIDE.md:192-200`), and `DATEADD(-1, YEAR)` becomes "last 12 months from today" (`:389-397`).
4. **Security semantics disappear.** PBI RLS roles are not parsed, and published AI/BI dashboards default to embedded credentials. Re-implement RLS as UC row filters or ABAC, and publish with viewer credentials where RLS matters.
5. **Validation must be numeric, not syntactic.** The app proves SQL *runs* (`converter.py:2944-2956`, `validator.py:189-214`) but never compares results with PBI. For an estate, build a reconciliation harness: the same filters and KPIs on both sides, with tolerances.
6. **Industrialize.** Convert shared semantic models once into metric views, point many dashboards at them, and batch-convert with review queues.

---

## 7. Patterns worth stealing

1. **Self-assuming UC IAM role.** Create the storage credential first, then build the trust policy from its external ID, wait for IAM, then create the external location (`aws-byovpc-uc/tf/unity_catalog.tf:1-115`).
2. **Poll-then-patch for eventually-consistent APIs, with fail-fast preconditions** (`aws-serverless-ncc/tf/s3_endpoint.tf:31-41, 50-66, 268-287`). Plus the `coalesce(unknown, lookup)` trick for single-apply convergence (`:91-108`).
3. **Destroy-time restore of a shared resource you only partly own** (bucket policy snapshot and restore, `s3_endpoint.tf:212-254`).
4. **Default-deny egress with explicit allow-lists** (`aws-byovpc-classic-privatelink/tf/network.tf:103-135`) and **service-endpoint policies** against exfiltration (§3.1 excerpt).
5. **Group-owned metastore** (`azure-vnet-injection-uc/tf/databricks.tf:44-71`).
6. **Wrap untrusted SQL as a subquery for validation.** `SELECT * FROM (<sql>) _t LIMIT 0` can't execute DDL (`converter.py:2948`). Quote LLM-supplied identifiers only through an allow-list regex (`color_utils.py:42-51`):
   ```python
   _SAFE_IDENT_RE = re.compile(r"^[A-Za-z0-9_ ]+$")


   def _quote_ident(name: str) -> str:
       """Backtick-quote an identifier, refusing anything that doesn't pass
       the conservative safe-identifier filter. Raises ValueError on refusal
       so callers see the bad input instead of silently producing []."""
       if not isinstance(name, str) or not _SAFE_IDENT_RE.match(name):
           raise ValueError(f"refusing to quote unsafe SQL identifier: {name!r}")
       return f"`{name}`"
   ```
7. **Truncation-aware LLM continuation** that detects incomplete JSON by brace balance, not only `finish_reason` (`converter.py:2219-2303`).
8. **Short-lived DB credentials per connection with pool recycling** below the token TTL (`orderflow-app-lakebase/app/server/db.py:17-50`).
9. **Rescue, then reconcile** for schema drift (`sdp-evolution/src/pipeline.py:19-28`, `reconcile.py:20-28`). Test the pure function in a job gate (`tests/test_reconcile_notebook.py`).
10. **Rebinding dashboard datasets per target** (`dataset_catalog`/`dataset_schema`, `customer360_dashboard.dashboard.yml:12-13`). Resource cross-references (`${resources.pipelines.x.id}`) instead of IDs.
11. **Job-scoped `run_as` when a bundle contains Apps** (`orderflow databricks.yml:77-83`):
    ```yaml
    # run_as is scoped to the job (not bundle-wide): apps must run as their owner,
    # so a bundle-level run_as would fail. The job runs as the CI/CD service principal.
    resources:
      jobs:
        orderflow_job:
          run_as:
            service_principal_name: ${var.run_as_sp}
    ```
12. **Agent runbooks with PAUSE gates** (`sql-server-cdc/RUNBOOK.md:33-43`, `sdp-evolution/README.md:19-30`). **Skills with a "why" changelog** (`dabs-migrator/CHANGELOG.md:1-5`).
13. **Report-only first, act later.** Resolution is ID→email with unresolved IDs listed, and errors are isolated per section (`aim-user-ownership-inventory`).

---

## 8. Risks, bugs, smells

Legend: **C** = CONFIRMED (read in code; "repro" = reproduced), **S** = SUSPECTED. Severity: H/M/L.

| # | Lbl | Sev | Where | Finding |
|---|---|---|---|---|
| R1 | C | H | all `terraform-examples/*/tf`; `aws-serverless-ncc/README.md:202-215` | No `backend`, so state is local with no locking or encryption. Multi-environment advice is `terraform workspace` on local state. |
| R2 | C | H | `aws/aws-byovpc/tf/metastore.tf:1-7`, `aws-byovpc-uc/tf/metastore.tf:7-13`, `aws-byovpc-classic-privatelink/tf/metastore.tf:1-7`, `aws-serverless-ncc/tf/metastore.tf:37-48`, `azure-vnet-injection-uc/tf/databricks.tf:44-52` | A region-wide metastore is created inside a per-workspace stack with `force_destroy = true`. Destroying that stack deletes a metastore other workspaces may share. |
| R3 | C | M | `aws/aws-byovpc/tf/network.tf:25-30, 39-76` + module v5.1.1 `modules/vpc-endpoints/main.tf:31`, `variables.tf:47-51` | STS and Kinesis interface endpoints get no SG, so AWS attaches the VPC default SG, which the module strips to zero rules. Calls resolved through private DNS are blocked. Runtime impact is inferred. The `-uc` fork fixes it at `aws-byovpc-uc/tf/network.tf:47`. |
| R4 | C | M | `aws-byovpc-classic-privatelink/tf/workspace.tf:1-9` | The IAM-propagation `time_sleep` depends on an empty `null_resource`, not on `aws_iam_role_policy`, so it does nothing. Compare the correct wiring at `aws-byovpc-uc/tf/workspace.tf:1-4`. The `null` provider is undeclared in `versions.tf`. |
| R5 | C | L | `aws-byovpc-classic-privatelink/tf/network.tf:10` vs `endpoints.tf:5` | Same module family pinned to 5.1.1 and 3.11.0. |
| R6 | C | L | `aws-byovpc-classic-privatelink/tf/variables.tf:35` vs `:205,235,238-242`; `providers.tf:22` | Region allow-list excludes `ap-southeast-3`, `us-west-1` and `us-gov-west-1`, which the endpoint maps define. GovCloud is also unreachable because of the commercial accounts host. |
| R7 | C | L | `aws/aws-byovpc/tf/variables.tf:33`; `aws-byovpc-uc/tf/unity_catalog.tf:11`; `aws-byovpc-classic-privatelink/tf/variables.tf:140`; `gcp-*/network.tf:1-2`; `pulumi…/requirements.txt:3` | Copy-paste error text ("resource_prefix must be … ENTERPRISE") plus dead locals, variables, data sources and dependencies. |
| R8 | C | M | `aws-byovpc-uc/tf/unity_catalog.tf:85,113,122`; `root_s3_bucket.tf:9` | `force_destroy` on buckets, external location and catalog. The catalog default name `"${var.prefix}-catalog"` contains hyphens (`:15`), so SQL needs backticks. |
| R9 | C | M | `aws-byovpc-uc/tf/unity_catalog.tf:43-45` | UC master-role ARN and `aws` partition are hard-coded, which breaks GovCloud and China. |
| R10 | C | L | `aws-byovpc-uc/tf/unity_catalog.tf:74-79`; `aws-serverless-ncc/tf/credential.tf:64-68` | `aws_iam_policy_attachment` is *exclusive* account-wide. Prefer `aws_iam_role_policy_attachment`. |
| R11 | C/S | M | `aws-byovpc-uc/tf/cluster.tf:18-20` | Hard-coded `r5d.large`. (S) `SINGLE_USER` without `single_user_name` binds to the deploying SP, so humans can't attach. Compare `azure-vnet-injection-uc/tf/cluster.tf:33-34`. |
| R12 | C | L | `aws-byovpc-uc/tf/outputs.tf:51` vs `workspace.tf:36` | The SG output logic differs from what the network actually uses (new VPC plus supplied SG IDs). |
| R13 | S | H | `aws-serverless-ncc/tf/s3_endpoint.tf:169-190`; `README.md:11` | Bucket policy is `Principal:*`, `s3:*`, conditioned only on `aws:SourceVpce`. Block Public Access treats SourceVpce-conditioned policies as non-public, so any request, including unsigned ones, routed through the NCC's endpoint is allowed, which could bypass UC. Scope it with `aws:PrincipalArn` = UC role and least actions. The README's "only … can reach" is wrong because an Allow restricts nothing. |
| R14 | C | M | `aws-serverless-ncc/tf/s3_endpoint.tf:21-27, 55-63, 123-130, 273-281`; `versions.tf:7` | Needs local `aws`, `jq` and `databricks` CLI, so it won't run in bare TFC or Atlantis runners. `ignore_changes=[enabled]` hides drift. Provider has no upper bound. |
| R15 | C | L | `aws-serverless-ncc/tf/providers.tf:20-22`; `variables.tf:105` vs `metastore.tf:30-36` | The workspace provider silently falls back to the accounts host. A variable description promises owner assignment the code deliberately doesn't do. |
| R16 | C | M | `azure-privatelink-classic/tf/databricks.tf:34` vs `terraform-examples/README.md:81` | `public_network_access_enabled = true` is hard-coded while the index claims "Optional public network access". |
| R17 | C | L | `azure-privatelink-classic/README.md:5, 80-81`; `service_endpoint_policy.tf:10-16` | README says "non–secure cluster connectivity", but `no_public_ip` defaults to `true` in azurerm ≥3.104 (provider docs) and the code doesn't override it. It also references a nonexistent `subnets_service_endpoints` variable, and a comment says `service="Global"` where the code uses `Microsoft.Storage`. |
| R18 | S | M | `azure-privatelink-classic/tf/ncc.tf:83-88` | `[...][0]` on PE connections read once, right after rule creation, with no wait. First apply can fail with "Invalid index". |
| R19 | C | L | `azure-privatelink-classic/tf/.terraform.lock.hcl` vs `.gitignore:7-8` | Lock-file policy is inconsistent. HashiCorp actually recommends committing lock files, so the root rule is the odd one out. |
| R20 | C | L | `azure-vnet-injection-uc/README.md:192,204,207` vs `tf/outputs.tf:5-8`, `tf/cluster.tf:33` | Docs reference a nonexistent `workspace_id` output and `var.data_security_mode`. |
| R21 | C | M | `azure-vnet-injection-uc/tf/unity_catalog.tf:13-26` | UC storage account keeps its public endpoint with no network rules and shared-key access on. Acknowledged at `README.md:159-163`. |
| R22 | C | M | `gcp-*/versions.tf:1-14` | Unpinned google and random providers, `databricks >=1.24`, no `required_version`. |
| R23 | C | H | `gcp-byovpc-*/service-account-impersonation.md:26-28, 85-101` | Token Creator granted at **project** scope, so the caller can impersonate *any* SA. The doc also downloads long-lived SA keys; use WIF or keyless ADC. |
| R24 | S | M | `gcp-byovpc-classic-psc/tf/dns.tf:23-36` | A private zone for all of `gcp.databricks.com` shadows every other Databricks hostname from this VPC. Each additional workspace needs its own records. |
| R25 | C | M | `terraform-examples/README.md:23-28, 60-63, 69-87, 139-144` | Claims "production-ready", but there are no cluster policies, CMK, grants, audit logs or IP ACLs. `aws-serverless-ncc` and `gcp-byovpc-shared-vpc` are missing from the index. Names a `*-cmk` scenario that doesn't exist. Requires `main.tf`, which most scenarios lack. |
| R26 | C | M | `powershell-examples/…/update_databricks_vnet.ps1:499-506, 458-464, 479-488` | Prints "Deployment initiated successfully" without checking `$LASTEXITCODE`. Dead `$deploymentParams`. Heuristic fills *any* `*name*` parameter with the workspace name. |
| R27 | C/S | M | `…/managed-vnet-to-vnet-injection/README.md:15` vs `:35`; `create_databricks_vnet.ps1:183-233` | "Creates everything needed", yet no outbound path (NAT). (S) NPIP clusters lose egress. |
| R28 | C | L | `temp-tools/S3 Policy Migration/README.md:28-34` vs `main.tf:29-47`; `modules/workspace_credentials/providers.tf:10-15` | Documented `bucket_arns_override` is never used, and one module is never called. A provider block inside a module is a legacy anti-pattern. `client_secret` goes in tfvars. |
| R29 | C | H | `aim-user-ownership-inventory/user_owned_objects_inventory.py:215-227, 469-475` | A failed scan section is printed as `[skip]`, yet the user is still listed as "safe to delete". That is a false negative. |
| R30 | S | M | same file `:238-298` | Jobs owned via `IS_OWNER` with no explicit `run_as` (created by someone else) and pipeline `run_as_user_name` are not checked. Genie spaces, Apps, serving endpoints and legacy SQL dashboards are not scanned. |
| R31 | C | L | `unity-catalog-abac/demo/README.md:204-206` | Advises deleting Terraform state, which orphans policies and tags. |
| R32 | C | L | `unity-catalog-abac/demo/setup.sql:31-37`; `demo/tf/providers.tf:9-15` | Hard-coded group→tenant mapping. CLI-profile (U2M) auth, so it can't run in CI. |
| R33 | C | M | `dbrx-business-semantics/dashboard_and_genie/genie_space.json:257-258, 290, 302-305` | Genie examples use nonexistent measures and label the median as "pct_of_relevance". |
| R34 | C | M | `dbrx-business-semantics/dashboard_and_genie/dashboard.lvdash.json:29,80`; `1_CreateMetricView.ipynb:149` | The dashboard `SUM`s the `total_amount` *dimension* instead of `MEASURE(sales_sum)`, re-implementing the metric in the BI layer. |
| R35 | C/S | M | `1_CreateMetricView.ipynb:249,254,171,463,371,395` | "Fiscal" synonyms on calendar fields. PII dimension. (S) `day_over_day_growth` divides without `NULLIF`/`try_divide`, risking `DIVIDE_BY_ZERO` under ANSI. Duplicate measures (Q2 = median, Q4 = max). |
| R36 | C | L | `2_QueryMetricView.ipynb:182-192`; `3_MaterializeMetricView.ipynb:84-513` | Internal `apiToken()` plus raw `requests`, although a `WorkspaceClient` exists. 300-line YAML copy-pasted between notebooks. |
| R37 | C (repro) | H | `pbi-aibi-converter/app_for_conversions/converter.py:2703-2719` | Aggregate promotion drops HAVING and ORDER BY-by-aggregate but keeps LIMIT, so top-N becomes N arbitrary raw rows. |
| R38 | C (repro) | H | `converter.py:2898-2915` vs `:93` | `_ensure_fqn_tables` rewrites **CTE references** to `catalog.schema.cte`, breaking the CTE pattern the prompt itself mandates for calculated tables. |
| R39 | C (repro) | H | `converter.py:2971-2990, 3052-3058` | The fuzzy column "fix" silently swaps in a different real column: `unit_cost→unit_count`, `order_date→order_rate`. It also replaces the token *everywhere* in the SQL. |
| R40 | C | M | `validator.py:332-356, 439, 473-475`; sample reports | `tableEx` (the PBI table visual; 6 in the samples) is absent from the type maps. Fidelity checks silently skip it, so dropped tables still "pass". |
| R41 | C | H | `app.py:422-509`; Lakeview API docs | Validation doesn't gate publish. `publish()` omits `embed_credentials`, whose API default is `true`, so viewers query as the app SP. Dashboards live in `/Workspace/Shared/aibi_converter` (`app.py:440-444`). |
| R42 | C | M | `app.py:168-195, 454-463` | Overwrite trashes any same-named dashboard in *any* folder the SP can see (the `fallback_id` path). |
| R43 | C | M | `converter.py:2397-2414` vs `:2466, 2477` | Chunked mode appends every batch and full JSON reply to the history, so the prompt size is not actually bounded by the chunk budget. |
| R44 | C | M | `knowledge/DAX_TO_SQL_GUIDE.md:5-17` vs `converter.py:92` vs `knowledge/AIBI_DASHBOARD_SKILL.md:57`; `CONVERSION_GUIDE.md:85` vs `converter.py:87`; `AIBI_DASHBOARD_SKILL.md:10-45`; `VISUAL_ALTERNATIVES_GUIDE.md:3,12-16` | Contradictory prompt knowledge: where measures go, global vs page filters. The prompt references MCP tools that don't exist in the app, and a nonexistent `alternatives.py`. It asks for non-schema `attributes` objects. |
| R45 | C | H | `DAX_TO_SQL_GUIDE.md:192-200, 389-397, 125-163, 350-357` | Wrong translations: `SUM(grand_total)` denominator; `DATEADD` becomes rolling 12 months from `current_date()`; CALCULATE override semantics lost; `LAG(…,12)` breaks when months are missing. |
| R46 | C | L | `README.md:35,47,65` vs `app.yaml:9-11`; `requirements.txt:1-5,13,15` | README says Claude Opus is the default, but the app ships Qwen with a hard-coded warehouse ID. The comment claims `~=` blocks minor versions, yet `~=1.50` and `~=1.39` allow them. |
| R47 | S | M | `converter.py:124-138, 371-376, 442-445`; `.streamlit/config.toml:2` | 1 GB uploads, `extractall`, temp directories never removed. Page and visual names from a crafted `.pbit` are used as filesystem paths, so path traversal is possible. |
| R48 | C | L | `README.md:73-82` | Documents only warehouse `CAN USE`. The SP also needs UC `USE`/`SELECT` for validation and write access to `/Workspace/Shared`. |
| R49 | S | L | `validator.py:189-203`; `converter.py:2946-2954` vs `color_utils.py:83-98` | No handling of `PENDING` state with a cold warehouse, so SQL is reported as failed. |
| R50 | C | L | `converter.py:1647-1956` vs `app.py:25-45,341`; `:2935` vs `:3036`; `validator.py:540` | Dead layout path. The docstring says 3 retries but the code does 5. Table coverage uses substring matching, producing false positives. |
| R51 | C/S | H | `sql-server-cdc/resources/ingestion_gateway.pipeline.yml:1-10`; `RUNBOOK.md:124-132` | The docs say the gateway "must be continuous" (`continuous: true`), but this bundle omits it and the runbook waits for completion. (S) CDC changes can be lost between runs. |
| R52 | C | M | `lakeflow-cdc-source-validator.ipynb:851-852, 924-928, 746` | The TDS probe sends a real password over TLS with `CERT_NONE`. The fallback sends LOGIN7 unencrypted, protected only by trivially reversible obfuscation. |
| R53 | C/S | M | `sdp-evolution/databricks.yml:4-5, 25-28`; `resources/pipeline.yml:8` | `skip_name_prefix_for_schema` means (S) developers collide in one schema. `PREVIEW` channel also applies to prod. The prod target has no host, `run_as` or permissions. |
| R54 | S (repro OSS) | L | `sdp-evolution/README.md:188`; `src/pipeline.py:16` | A JSON number read into a STRING column is coerced, not rescued, so v2 `amount` is probably not null. |
| R55 | C | M | `customer-360…/src/pipeline/03_gold.sql:44-45`; `generate_data.py:136` | "At risk" and `arr_at_risk` come from the generator's planted `is_cohort` flag, not the computed churn score. |
| R56 | C | H | `customer-360…/src/metric_view/mv_customer_health.py:40-43` over `03_gold.sql:52-94` | Snapshot measures (`account_count`, `arr_total`) are SUM-ed over a daily spine. Any multi-day query multiplies them; they need semi-additive windows. |
| R57 | C | M | `customer-360…/databricks.yml:57-58`; `.github/workflows/deploy.yml:36-57, 74-95`; `AGENTS.md:140-154` | Dev has no `mode: development`, so every feature branch deploys over the same dev bundle. Prod deploys on push to main with no approval environment or `concurrency`, and re-runs the data-overwriting setup job every time. (S) The teardown note contradicts that schema and volume are bundle resources. |
| R58 | C | M | `customer-360…/.github/workflows/deploy.yml:46,69,83`; `.gitlab-ci.yml:21`; `Jenkinsfile:21`; `azure-pipelines.yml:33`; `orderflow…/.github/workflows/*.yml:16,39`; `dabs-migrator/…/cicd/github-actions.md:32`; `.github/workflows/release.yml:16,37` | Floating supply-chain refs: `setup-cli@main`, `cli:latest`, `curl … main/install.sh | sh`, actions pinned by tag not SHA. |
| R59 | C | H | `dabs-migrator/…/templates/databricks.yml.tmpl:43,53` vs docs ("You cannot specify custom variables for these authentication values") and `customer-360…/databricks.yml:60-62` | The template sets `workspace.host: ${var.workspace_host}`, which contradicts the docs and a sibling project. |
| R60 | C | M | `dabs-migrator/…/templates/requirements.txt.tmpl:4`; `templates/test_unity_catalog.py:1-22` | Pins the deprecated legacy `databricks-cli` pip package. The "tests" are `assert True`. |
| R61 | C | M | `dabs-migrator/…/SKILL.md:3,200-204` vs `:64,128`; `:126` vs `sdp-evolution/resources/pipeline.yml:14-17`, `orderflow…/resources/pipeline.yml:15-17`; `resources/genie_spaces.md:9` vs `:37` | Self-contradictions: stubs vs verbatim copy; `.py`→`notebook:` vs plain-`.py` `file:` used elsewhere in the repo; `file_path` JSON vs `${var}` substitution, which customer-360 says isn't applied inside `file_path`. |
| R62 | C | L | `.github/workflows/release.yml:20-30` | Every change to the skill cuts a new *major* version. The `sed` only parses `vN.0`. |
| R63 | C (repro) | H | `.gitignore:1`; `orderflow…/app/frontend/package.json:8`; `ci.yml:34-38`; `deploy.yml:32-36` | `*conf*.json` ignores `tsconfig*.json`, so `tsc -b` fails with TS5083 and CI and deploy are broken from a clean clone. |
| R64 | S | H | `orderflow…/app/app.py:40-45` | The SPA catch-all does `FileResponse(os.path.join(dist, full_path))` with no containment check. Path traversal could reach source or `/proc/self/environ` (the app SP secret). Unverified behind the Apps proxy. |
| R65 | C | M | `orderflow…/.github/workflows/deploy.yml:41-45`; docs "bundle run <app>" | CI never runs `bundle run orderflow_app`, so new app code isn't rolled out. It masks job failure with `|| true`. |
| R66 | C/S | M | `orderflow…/databricks.yml:48,62`; `deploy.yml:20-24`; `resources/lakebase.yml:29-39` | Dev and prod point at the same Lakebase project, endpoint and credentials. (S) Two bundle targets manage one project. The DB owner is a human role. |
| R67 | C | M | `orderflow…/app/server/routes/orders.py:79-93`; `scripts/schema.sql:11` | Time-of-check/time-of-use (TOCTOU) race on the stock check. `CHECK (stock>=0)` prevents oversell, but callers get a 500 instead of a 400. Use `UPDATE … WHERE stock >= q` or `SELECT … FOR UPDATE`. |
| R68 | C | M | `orderflow…/jobs/ingest_lakebase.py:35-50`; `pipeline/transformations.py:54`; `jobs/daily_rollup.py:35` | Full-table `fetchall` onto the driver, every value `str()`-ed, so money is computed as double. The rollup is `append` and CI re-runs it on every deploy, creating duplicate snapshots. |
| R69 | C | L | `CODEOWNERS.txt:1`; `CONTRIBUTING.md:1-4,27,85`; `README.md:11-16,64`; `.pre-commit-config.yaml:1-7` | CODEOWNERS has the wrong filename and no patterns, so it is inert. CONTRIBUTING is a PR description ("six-category" but lists 7; references a missing `question.yml`). The README lists only the new tracks and links a missing `LICENSE-THIRD-PARTY.md`. The LicenseFinder hook has no decisions file and no CI enforcement. |
| R70 | S | L | `pulumi-examples/azure/azure-hybrid/__main__.py:44`; `requirements.txt:2` | `compute_mode="Hybrid"` may not exist in pulumi-azure-native <3's default API version. Verify with `pulumi preview`. |

No real secrets are committed; I grepped for PAT, AKIA and password patterns and found only placeholders. Environment-specific identifiers do leak: a warehouse ID in `pbi-aibi-converter/app_for_conversions/app.yaml:9` and an internal catalog name in `dabs-migrator/docs/superpowers/specs/2026-08-05-dabs-migrator-test-harness-design.md:44`.

---

## 9. How to explain each major project

| Project | (a) Customer executive | (b) Customer platform engineer | (c) Internal stakeholder (account team, PS) |
|---|---|---|---|
| Terraform workspace setup | "A repeatable, auditable blueprint for a private, governed Databricks estate in days, not months. Same security posture every time." | "Flat roots per scenario. Account provider for mws objects, workspace provider for UC. Back-end PL/PSC plus restricted egress. You add a remote backend, module wrapping, cluster policies and CMK before prod." | "Accelerates onboarding and security reviews. Good for first-time Terraform customers. Point security-heavy accounts to SRA. Watch the metastore-in-stack and `force_destroy` defaults." |
| UC ABAC | "Sensitive data is protected automatically the moment it lands, with no per-table tickets, and audit can see one policy per rule." | "Governed tags plus Data Classification, then `CREATE POLICY … MATCH COLUMNS has_tag()`. Functions are pure; `TO`/`EXCEPT` groups decide who. Needs DBR 16.4+ or serverless. Verify with `SHOW EFFECTIVE POLICIES`." | "Governance flagship demo. Runs in 20 minutes, but the first query returns 0 rows by design, and the Terraform needs a CLI profile. Upsell: Data Classification, serverless." |
| PBI → AI/BI converter | "Moves the Power BI report estate onto the lakehouse, cutting licensing and data copies. Each dashboard needs review, not rebuild." | "LLM plus deterministic layout and SQL repair. Requires data in UC. Check DAX-heavy measures and RLS manually. Publish with viewer credentials if you need RLS." | "Great for pipeline and demos. Position as '70% draft + review', not a push-button migration. Fix R37–R45 before large pilots. Tie to a metric-view strategy." |
| Business semantics (metric views) | "One definition of revenue across dashboards, SQL and AI, so numbers match in every meeting." | "`CREATE VIEW … WITH METRICS` YAML: joins, dimensions, measures, semi-additive windows, synonyms. `MEASURE()` to query. Optional scheduled materialization." | "Anchor for BI consolidation and Genie accuracy. Coach customers on synonym hygiene and on keeping PII out of Genie dictionaries." |
| Lakeflow Connect + validator + SDP evolution | "Managed CDC from operational databases without custom code. Pipelines survive upstream schema changes without outages." | "UC connection, then a continuous gateway on classic compute, then a serverless ingestion pipeline. Pre-flight DNS, TCP and TLS from the gateway's network. Fixed bronze schema plus rescue, then reconcile in silver." | "Reduces ingestion-POC failure. Most escalations are network and CDC setup, so run the validator first. Correct the gateway `continuous` setting." |
| CI/CD (customer-360, dabs-migrator, orderflow) | "Every change is reviewed, tested and promoted the same way, so fewer production incidents and a clean audit trail." | "DABs targets dev, staging and prod. SP OAuth M2M, `run_as` SP, a `permissions` block, PR = validate, prod gated by approval. Expect Genie's 3-phase deploy. The migrator turns UI assets into code." | "Standard 'from notebooks to engineering' motion. The skill plus its changelog is a repeatable AI-assisted services offering. Validate, then deploy to dev, before claiming done." |
| AIM ownership inventory | "Identity cleanup without breaking production jobs or losing work when people leave." | "Run per workspace on the flagged IDs. Transfer `IS_OWNER`/`run_as` to SPs. Handle UC ownership separately with `ALTER … OWNER TO`." | "De-risks AIM enablement. Pair it with an ownership policy (group/SP owners). Note the false-negative risk when scans are skipped (R29)." |

---

## 10. Interview-prep angles

**Q1. How would you set up a new customer's Databricks platform securely?**
Work in three layers, in this order.

1. **Account.**
   * SSO plus SCIM or AIM.
   * Groups for every role.
   * Automation through OAuth M2M SPs, with no PATs.
   * One metastore per region owned by an admin group, kept in its own IaC state.
2. **Network, per workspace.**
   * BYO VPC/VNet with SCC/NPIP.
   * Back-end PrivateLink/PSC for REST and relay.
   * Egress denied by default, allowing only NAT or endpoints: S3/STS/Kinesis endpoints on AWS; service-endpoint policy and DBFS firewall on Azure.
   * Private DNS.
   * An NCC for the serverless plane.
   * Front-end PL or IP ACLs where required.
3. **Data and governance.**
   * Catalogs per domain or environment, each on its own storage via storage credentials and external locations.
   * Grants to groups.
   * Governed tags plus ABAC for PII.
   * Cluster and budget policies; audit logs and system tables; CMK if regulated.

Deliver it all with Terraform, using a remote locked backend and plan review, and DABs for workloads. This repo covers layer 2 and part of 3. You add the state backend, policies, CMK and grants (§4, R1, R25).

**Q2. How do you implement row-level security in UC?**
There are two ways.

* *Per table*: write a SQL UDF returning BOOLEAN, for example `is_account_group_member(...)` or a lookup against a mapping table, then `ALTER TABLE t SET ROW FILTER f ON (tenant_col)`.
* *At scale*: create a governed tag, tag the tenant column (`SET TAGS`), then `CREATE POLICY … ON SCHEMA|CATALOG ROW FILTER f TO \`account users\` EXCEPT admins FOR TABLES MATCH COLUMNS has_tag_value('rls','tenant') AS c USING COLUMNS (c)`.

Test as a non-admin, and remember admins aren't exempt unless you add `EXCEPT` (`unity-catalog-abac/README.md:250-282`). Watch for dashboards published with embedded credentials, where the filter evaluates for the publisher.

**Q3. How do you promote code from dev to prod?**
Use DABs with `dev` (development mode, user-prefixed, schedules paused), `staging` and `prod` (production mode, `root_path` under `/Shared`, `run_as` an SP, `permissions` block).

1. A PR runs `bundle validate`.
2. Merging to main deploys to staging and runs tests.
3. A tag or approval deploys to prod with the prod SP's OAuth credentials from the CI secret store.

Keep one SP per environment and isolate environments at the workspace or catalog level. Pin CLI versions and add `concurrency` so deploys don't race. This repo's customer-360 flow adds a 3-phase deploy for Genie (§3.7). The dabs-migrator template gates prod on `environment: prod` (§3.7).

**Q4. How would you migrate a Power BI estate?**

1. **Inventory and triage**: counts, DAX complexity, RLS roles, sources.
2. **Land data in UC**: Lakeflow Connect or federation.
3. **Rebuild shared semantic models as metric views.**
4. **Convert reports.** The converter here does pixel→grid layout, visual mapping and LLM DAX→SQL with executability checks.
5. **Re-implement RLS** as UC row filters or ABAC. Publish with viewer credentials where needed.
6. **Reconcile numbers** against PBI for key KPIs under several filters.
7. **Train users; decommission in waves.**

Expect the effort to go into DAX filter-context semantics, not layout.

**Q5. `databricks_grants` vs `databricks_grant`?**
The plural is authoritative. It replaces *all* grants on the securable and can revoke the deploying SP's own implicit privileges if applied at the wrong time (`aws-serverless-ncc/tf/credential.tf:78-83`). The singular adds one principal's privileges. Use the plural where Terraform owns the whole ACL, the singular for shared securables.

**Q6. Why create the storage credential before its IAM role?**
The UC trust policy must contain the credential's **external ID**, which exists only after the credential is created. Create the credential with the future role ARN, generate the trust policy from its external ID, create the role, wait for IAM propagation, then create the external location. Otherwise validation fails with AccessDenied (`aws-byovpc-uc/tf/unity_catalog.tf:1-115`).

**Q7. How does serverless reach private storage if it isn't in my VPC?**
Through a **Network Connectivity Configuration** bound to the workspace. Private-endpoint rules make Databricks create endpoints in its serverless network: S3 VPCE on AWS; blob and dfs private endpoints on Azure, which you approve. You then allow that endpoint in the bucket policy (`aws:SourceVpce`) or approve the PE on the storage account. That is exactly what `aws-serverless-ncc` and `azure-privatelink-classic/tf/ncc.tf` automate.

**Q8. A pipeline broke after an upstream column rename. What do you do without a full refresh?**
Pin the bronze schema, enable Auto Loader `schemaEvolutionMode=rescue` with `_rescued_data`, and fix forward in silver with a `coalesce(base, from_json(_rescued_data).new_name)` mapping. Keep the mapping as a tested pure function. Watch type coercion: numbers read into string columns aren't rescued (`sdp-evolution`, R54).

**Q9. Why metric views instead of views or BI-tool models?**
Measures are defined once, with correct aggregation semantics: ratios as ratio-of-sums, semi-additive windows, YTD. They are governed in UC, carry agent metadata (synonyms, formats) for Genie, and can be materialized. Views can't express "measure" semantics, and BI-tool models lock definitions inside one tool. The customer-360 bug R56 shows why semi-additivity matters.

**Q10. How do you debug "Databricks can't reach my database"?**
Walk the layers:

1. DNS resolution from the *same compute plane* the connector uses (classic gateway vs serverless).
2. TCP to host:port, distinguishing a timeout (SG/NACL/firewall) from a refusal (service or port).
3. TLS inside the protocol.
4. Auth with a trivial query.

Get the egress IP to allowlist. The validator notebook automates this (§3.5).

**Q11. The deploy passed `bundle validate` but failed in prod. Why?**
Validate checks schema and variable resolution only. Deploy-time API checks catch empty optional objects, ID formats and name constraints (dabs-migrator `CHANGELOG.md:30-47`). Also:

* Validate each *target*: undeclared variables only fail for staging and prod (`:51-61`).
* Genie spaces need their tables to exist at deploy time.

Mitigate with a dev deploy in CI and smoke tests.

**Q12. How does this scale to 50 workspaces?**

* Separate account-level singletons (metastore, NCC, groups) from per-workspace stacks.
* Turn the flat roots into modules driven by `for_each` over a workspace map.
* Use remote state with locking, per-environment pipelines and policy-as-code (checkov/OPA).
* Standardize catalog-per-domain with ABAC at catalog scope.
* DAB per product with shared templates. The dabs-migrator skill turns UI sprawl into code.

**Q13. How do you make AI-generated SQL safe to execute?**

* Never execute raw output. Wrap it as `SELECT * FROM (<sql>) LIMIT 0` so DDL/DML can't run.
* Run as a least-privilege identity.
* Allow-list identifiers (`color_utils.py:42-51`).
* Prefer failing over "auto-fixing" semantics (R39).
* Verify results numerically against a reference.

**Q14. Who owns what, and why does it matter when people leave?**
Jobs run as their owner unless `run_as` is set. Home folders are deleted with the user. PATs die with the user. UC objects have a single owner with grant rights. Assign ownership to groups or SPs, inventory before deprovisioning (`aim-user-ownership-inventory`), and treat "no findings" as valid only if every scan section succeeded (R29).

---

## 11. AI-stewardship angle

The repo is itself a case study: several projects are agent runbooks or skills, and one is an LLM application. The failure modes it documents, or exhibits, generalize.

**Terraform.**

* AI tends to wire provider dependencies wrongly. Here, a `time_sleep` depends on an empty `null_resource` (R4).
* It copies registry snippets across module versions (R5).
* It drops SG associations: STS/Kinesis endpoints landed on a deny-all default SG (R3).
* It hard-codes ARNs and partitions (R9).
* It sprinkles `force_destroy` (R2, R8).
* It invents or misremembers defaults: the README believed `no_public_ip=false` (R17).

Check with `terraform fmt`, `terraform validate`, and `terraform plan -out` reviewed for *every* destroy and replace. Add tflint plus checkov or tfsec (open SGs, `Principal:*` policies, missing encryption), `terraform graph` for ordering, `terraform providers lock`, and read the upstream module source for defaults, as I did for R3.

**UC grants.**

* AI mixes up authoritative and additive resources (R/§5).
* It forgets `USE CATALOG`/`USE SCHEMA`.
* It grants to users instead of groups.
* It leaves new catalogs with no grants.

Check with `SHOW GRANTS ON CATALOG x`, `SHOW GRANTS \`group\` ON SCHEMA …`, `system.information_schema.table_privileges`/`schema_privileges`, and a test query run *as a non-admin principal*.

**ABAC, masks and filters.**

* AI puts identity logic inside mask functions (fine for classic masks, redundant under ABAC).
* It forgets `EXCEPT` for break-glass admins or assumes admins are exempt.
* It uses non-governed tags.
* It writes RLS predicates that don't scale.

Check with `SHOW EFFECTIVE POLICIES ON TABLE`, `DESCRIBE POLICY`, `system.information_schema.column_tags` (tags actually present), and queries under two test identities with different memberships.

**DAB YAML.**

* AI uses `../src` from nested resource folders.
* It picks `notebook:` vs `file:` library kinds wrongly. Note the repo *disagrees with itself* here (R61).
* It uses legacy `target:` instead of `schema:`.
* It interpolates variables where the docs forbid them (R59).
* It copies live IDs verbatim.
* It emits empty optional blocks.
* It drops `pause_status`, re-activating schedules (dabs-migrator `CHANGELOG.md:51-63`).

Check with `databricks bundle validate -t <every target>`, `databricks bundle summary`, a real `bundle deploy` to a dev workspace, a diff of the migrated YAML against a live read, and `bundle run` smoke tests.

**LLM-generated artifacts: the PBI converter lesson.**

* Deterministic repair code can turn a *loud* failure into a *silent* wrong answer: fuzzy column substitution (R39), HAVING/LIMIT rewriting (R37), CTE rewriting (R38).
* Contradictory knowledge documents in one prompt yield nondeterministic behaviour (R44).
* A validator that skips unknown types reports false success (R40).
* The cookbook itself can be wrong (R45).

Stewardship practices:

* Unit-test every rewrite with adversarial SQL, as I did with `sqlglot 26.33`.
* Fail closed: surface an error rather than "fix" it.
* Gate publish on validation.
* Add **numeric reconciliation** against the source system.
* Keep one authoritative instruction per topic.
* Record *why* rules exist, as dabs-migrator's changelog does.

**Agent runbooks.** PAUSE gates, "do not invent credentials", "wait for SUCCESS", and "every step green before next" are good guardrails (`sdp-evolution/README.md:19-30`). But an agent following a runbook that is wrong about product behaviour will faithfully do the wrong thing: RUNBOOK waits for a continuous gateway to COMPLETE (R51). Keep runbooks in sync with the docs, and cite the doc for each behavioural claim.

**Repo hygiene.** One broad ignore rule (`*conf*.json`) silently removed files an AI-scaffolded Vite project needs (R63). Check `git check-ignore -v`, and build from a clean clone in CI.

---

## 12. Glossary

* **ABAC (UC):** attribute-based access control. Policies at catalog or schema scope match governed tags (`has_tag`, `has_tag_value`) and apply row filters or column masks to `TO`/`EXCEPT` principals.
* **Access connector (Azure):** a Databricks-managed identity used by UC storage credentials and the DBFS firewall.
* **Account vs workspace provider:** Terraform Databricks provider aliases for account-level APIs (workspaces, networks, metastores, NCC, identities) vs in-workspace APIs (UC objects, clusters, grants).
* **AI/BI dashboard (Lakeview):** Databricks dashboards defined as `.lvdash.json` (datasets plus pages plus widgets on a 6-column grid). Published with embedded or viewer credentials.
* **AIM:** Automatic Identity Management; Databricks identity sync with Microsoft Entra ID keyed on Object ID.
* **Auto Loader (`cloudFiles`):** incremental file ingestion. `schemaEvolutionMode=rescue` puts drift into `_rescued_data`.
* **Back-end PrivateLink / PSC:** private connectivity from the classic compute plane to the control plane (REST API and SCC relay endpoints). Front-end PL covers users→UI.
* **BYOVPC / VNet injection:** deploying classic compute into a customer-managed network.
* **CMK:** customer-managed keys for managed services or storage; absent from this repo.
* **DAB:** Databricks Asset Bundles, renamed Declarative Automation Bundles (`sql-server-cdc/RUNBOOK.md:13`). Project-as-code with targets, variables, resources, `validate`/`deploy`/`run`.
* **DAX / TMDL / TMSL / PBIR / .pbip / .pbit:** Power BI's measure language, semantic-model text formats (TMDL is folder-based, TMSL is JSON), report-definition format, project folder format, and template file.
* **Data Classification:** an agentic scanner that applies system governed tags (`class.*`) to sensitive columns.
* **Embedded credentials:** the published-dashboard mode where queries run as the publisher (the API default is `true`).
* **External location / storage credential:** a UC securable pairing a cloud path with the credential (IAM role or managed identity) used to access it.
* **Genie space:** a natural-language-to-SQL room over UC tables and metric views, with instructions, examples and value dictionaries.
* **Governed tag:** an account-level tag with a policy (allowed values, who may `ASSIGN`).
* **Identity federation:** account-level identities assigned to workspaces (`mws_permission_assignment`).
* **Ingestion gateway / ingestion pipeline:** the Lakeflow Connect CDC pair. The gateway runs continuously on classic compute and stages changes; the pipeline runs serverless and applies them to streaming tables.
* **Lakebase:** Databricks-managed Postgres (projects, branches, endpoints, roles) with OAuth-minted DB credentials.
* **Materialized view (SDP):** a batch-recomputed dataset in a declarative pipeline. A streaming table is its incremental counterpart.
* **Metastore:** the top UC container, one per region per account, assigned to workspaces.
* **Metric view:** a UC view `WITH METRICS LANGUAGE YAML` holding dimensions, measures, joins, windows and semantic metadata, queried with `MEASURE()`.
* **NCC:** Network Connectivity Configuration; the account object controlling serverless egress (stable IPs, private endpoint rules).
* **NPIP / SCC:** no-public-IP / secure cluster connectivity. Nodes have no public IPs and dial out to a relay.
* **PAS:** Private Access Settings; the AWS/GCP object governing public access and PL scope (`ACCOUNT` or `ENDPOINT`).
* **Row filter / column mask:** SQL UDF-based fine-grained controls attached per table, or via ABAC.
* **SDP:** Spark Declarative Pipelines (formerly DLT, "Lakeflow Declarative Pipelines"), `pyspark.pipelines`/`dlt`.
* **Securable hierarchy:** metastore, then catalog, then schema, then table, view, volume, function, model or metric view. Plus credentials, external locations, connections and shares.
* **Service endpoint policy (Azure):** restricts `Microsoft.Storage` service-endpoint traffic to listed storage accounts or aliases; an exfiltration control.
* **Semi-additive measure:** a measure that must not be summed across some dimension (usually time), such as balances and headcount.
* **SRA:** Databricks Security Reference Architecture Terraform templates (`terraform-examples/README.md:17-19`).
* **Terraform backend / state locking:** where state lives (S3, azurerm, GCS, TFC) and how concurrent applies are prevented (DynamoDB or native lockfile, blob lease).
