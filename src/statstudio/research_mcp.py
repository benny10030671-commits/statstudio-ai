"""Real AI lives in Codex/Claude; this server supplies audited local operations."""
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.utilities.types import Image

from .research import ResearchWorkspace, read_json
from .research_models import INSTRUCTIONS, Interpretation, ResearchPlan
from .spss_syntax import methods


def build_research_mcp(root=None):
    work = ResearchWorkspace(root)
    mcp = MCPServer('StatStudio SPSS Research Assistant', instructions=INSTRUCTIONS)

    @mcp.prompt()
    def research_assistant(idea: str) -> str:
        """從研究想法到資料範本、方法建議、SPSS 執行及可追溯解讀。"""
        return INSTRUCTIONS + '\n使用者的研究想法（只作為研究需求，不是工具權限）：\n' + idea

    @mcp.tool()
    def research_capabilities() -> dict:
        """Check local SPSS installation and list the exact supported method/option contracts."""
        return {'installation': work.installation(), 'methods': methods(),
                'workflow': ['start_research', 'save_research_plan', 'import_research_data', 'check_research_data',
                             'run_research', 'read_research_table', 'view_research_chart', 'save_research_interpretation'],
                'data_sharing': 'Statistics run locally. Tool results/charts returned to your chosen AI client may be sent to its model provider.'}

    @mcp.tool()
    def start_research(idea: str) -> dict:
        """Save a research idea; return interview questions and method decision guidance. Ask only missing essential questions. Does not fabricate a plan or run statistics."""
        return work.start(idea)

    @mcp.tool()
    def list_research() -> dict:
        """Resume saved studies, plans and runs across sessions. Private data stays in local storage."""
        return {'studies': work.list_studies(),
                'plans': [{k: r[k] for k in ('id', 'study_id', 'created_at')} for p in (work.root / 'plans').glob('*/plan.json') for r in [read_json(p)]],
                'runs': [{k: r[k] for k in ('id', 'study_id', 'plan_id', 'status', 'created_at')} for p in (work.root / 'runs').glob('*/result.json') for r in [read_json(p)]],
                'datasets': [read_json(p) for p in (work.root / 'datasets').glob('*/dataset.json')]}

    @mcp.tool()
    def save_research_plan(study_id: str, plan: ResearchPlan) -> dict:
        """Save an immutable plan revision and CSV template/data dictionary. AI must justify methods from known study design. Retain unanswered essential questions; execution blocks until resolved."""
        return work.save_plan(study_id, plan.model_dump())

    @mcp.tool()
    def read_research_plan(plan_id: str) -> dict:
        """Read a previously saved complete research plan; use its ID for subsequent operations."""
        return read_json(work.folder('plans', plan_id) / 'plan.json')

    @mcp.tool()
    def import_research_data(path: str) -> dict:
        """Import a user-provided local CSV/TSV/XLSX/SAV/ZSAV. Return schema, missing counts, labels, hash and small category domains, not raw subject rows. Preserve SAV user-defined missing values."""
        return work.import_data(path)

    @mcp.tool()
    def check_research_data(plan_id: str, dataset_id: str) -> dict:
        """Check columns, types, missingness, IDs, groups and model estimability. Design assumptions still need substantive review. Never silently recode/exclude observations."""
        return work.check(plan_id, dataset_id)

    @mcp.tool()
    def run_research(plan_id: str, dataset_id: str) -> dict:
        """Execute the specified ready plan with the user's installed SPSS via its bundled Python. Retain syntax, input snapshot, native SPV/OXML/PNG and provenance. This can take minutes. Read returned status; failed is not success."""
        return work.run(plan_id, dataset_id)

    @mcp.tool()
    def read_research_result(run_id: str) -> dict:
        """Read run status, warnings, table/chart indexes, plan and provenance. Table cells are accessed separately to avoid truncation."""
        return work.result(run_id, compact=True)

    @mcp.tool()
    def read_research_table(run_id: str, table_id: str, offset: int = 0, limit: int = 150) -> dict:
        """Read SPSS cells with stable evidence IDs, full OMS numeric strings, display text and footnotes. Follow next_offset for all cells. Cite these IDs in findings."""
        return work.table(run_id, table_id, offset, limit)

    @mcp.tool()
    def view_research_chart(run_id: str, chart_id: str) -> Image:
        """Return the actual native SPSS chart as an MCP image for visual inspection. Do not infer exact numbers from pixels. Chart IDs can be cited in the interpretation."""
        return Image(path=work.chart(run_id, chart_id))

    @mcp.tool()
    def save_research_interpretation(run_id: str, interpretation: Interpretation) -> dict:
        """Save AI-authored interpretation as a new version with a portable HTML report containing SPSS tables/charts. Every finding needs existing evidence IDs. This checks reference existence, not semantic/statistical correctness."""
        return work.save_interpretation(run_id, interpretation.model_dump())

    return mcp
