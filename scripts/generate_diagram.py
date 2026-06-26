from diagrams import Diagram, Cluster, Edge
from diagrams.onprem.vcs import Github
from diagrams.onprem.inmemory import Redis
from diagrams.onprem.monitoring import Grafana
from diagrams.onprem.workflow import Airflow
from diagrams.programming.language import Python
from diagrams.onprem.client import User

graph_attr = {
    "pad": "1.5",
    "splines": "ortho",
    "nodesep": "1.0",
    "ranksep": "1.5",
    "fontsize": "28",
    "bgcolor": "#0d1117",
    "fontcolor": "#c9d1d9",
}

node_attr = {
    "fontsize": "13",
    "fontname": "Helvetica",
}

edge_attr = {
    "fontsize": "10",
    "fontname": "Helvetica",
    "color": "#8b949e",
}

with Diagram(
    "On-Call Autopilot Architecture",
    filename="architecture",
    direction="TB",
    show=False,
    outformat=["png"],
    graph_attr=graph_attr,
    node_attr=node_attr,
    edge_attr=edge_attr,
):
    with Cluster("GitHub"):
        gh_repo = Github("Repository\n(salginci/oncall-autopilot)")

    with Cluster("Alibaba Cloud"):
        with Cluster("ECS Instance"):
            with Cluster("Docker Compose"):
                with Cluster("On-Call Autopilot Agent :8080"):
                    fsm = Python("State Machine\n══════════════════\nIDLE → RECEIVED → TRIAGING\n→ INVESTIGATING → REMEDIATING\n→ WAITING_APPROVAL → RESOLVED")

                demo = Python("Demo Service :3000\n══════════════════\nSimulated Microservice\nConfigurable DB Pool\n/metrics /health /admin/reload")

        redis = Redis("ApsaraDB Redis\n═══════════\nIncident State Store\nActive/Pending Incidents")

        sls = Grafana("SLS Logging\n═══════════\nStructured JSON\nTrace IDs")

    with Cluster("Qwen Cloud"):
        qwen = Airflow("Qwen API\n══════════\nTriage Agent\nInvestigate Agent\nRemediate Agent")

    human = User("Human Operator\n═══════════\nocli approve/deny/status")

    loadgen = Python("Load Generator\n═══════════\n15 Concurrent Threads\n~200 req/s")

    # Flow connections
    gh_repo >> Edge(label="bad commit pushed\n(triggers incident)", color="#f85149", style="bold") >> demo
    loadgen >> Edge(label="hits API endpoints", style="dashed", color="#58a6ff") >> demo

    demo >> Edge(label="error rate spike", color="#f85149") >> fsm
    fsm >> Edge(label="triage call (Qwen)", color="#d2a8ff") >> qwen
    fsm >> Edge(label="investigation (Qwen)", color="#d2a8ff") >> qwen
    fsm >> Edge(label="remediation (Qwen)", color="#d2a8ff") >> qwen
    qwen >> Edge(label="analysis + fix plan", color="#d2a8ff") >> fsm

    fsm >> Edge(label="save/load state", style="dashed") >> redis
    fsm >> Edge(label="log events (JSON)", style="dotted") >> sls
    demo >> Edge(label="log requests (JSON)", style="dotted") >> sls

    fsm >> Edge(label="await approval", color="#d29922") >> human
    human >> Edge(label="approve/deny", color="#3fb950") >> fsm

    fsm >> Edge(label="POST /admin/reload", style="dashed") >> demo
    fsm >> Edge(label="revert commit + push", color="#3fb950") >> gh_repo
