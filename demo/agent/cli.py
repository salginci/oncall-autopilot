import json
import httpx
import sys
import time
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

app = typer.Typer(help="On-Call Autopilot CLI — human-in-the-loop approval interface")
console = Console()

AGENT_URL = "http://localhost:8080"


def fetch_json(path: str) -> dict:
    try:
        resp = httpx.get(f"{AGENT_URL}{path}", timeout=5.0)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def post_json(path: str, params: dict = None) -> dict:
    try:
        resp = httpx.post(f"{AGENT_URL}{path}", params=params, timeout=10.0)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


@app.command()
def status():
    """List active incidents and pending approvals"""
    data = fetch_json("/api/incidents")
    if "error" in data:
        console.print(f"[red]Agent not reachable: {data['error']}[/red]")
        return

    pending = data.get("pending_approvals", [])
    active = data.get("active_incidents", [])

    console.print(Panel.fit("[bold]On-Call Autopilot Status[/bold]", border_style="blue"))

    if pending:
        console.print(f"\n[bold yellow]⚠  Pending Approvals: {len(pending)}[/bold yellow]")
        for inc_id in pending:
            console.print(f"  ⏳ {inc_id}")
            details = fetch_json(f"/api/incidents/{inc_id}")
            if "incident_id" in details:
                alert = details.get("alert", {})
                root_cause = details.get("root_cause", {})
                remediation = details.get("remediation", {})
                console.print(f"     Service: {alert.get('service', '?')}")
                console.print(f"     Severity: [bold]{details.get('severity', '?')}[/bold]")
                if root_cause:
                    console.print(f"     Root Cause: {root_cause.get('summary', '?')}")
                if remediation:
                    console.print(f"     Proposed Fix: [green]{remediation.get('action', '?')}[/green]")
                    console.print(f"     Risk: [bold]{remediation.get('risk', '?')}[/bold]")

    if active:
        console.print(f"\n[bold]Active Incidents: {len(active)}[/bold]")
        for inc_id in active:
            console.print(f"  🔴 {inc_id}")
    elif not pending:
        console.print("\n[green]No active incidents. System healthy.[/green]")


@app.command()
def approve(incident_id: str):
    """Approve a remediation plan"""
    result = post_json(f"/api/incidents/{incident_id}/approve")
    if result.get("success"):
        console.print(f"[bold green]✓ Approved[/bold green] Incident {incident_id}")
        console.print(f"  Details: {json.dumps(result.get('details', []), indent=2)}")
    else:
        console.print(f"[bold red]✗ Failed:[/bold red] {result.get('error', 'unknown')}")


@app.command()
def deny(incident_id: str, override: str = typer.Option("", help="Optional manual override fix")):
    """Deny a remediation plan, optionally with a manual override"""
    params = {}
    if override:
        params["override"] = override
    result = post_json(f"/api/incidents/{incident_id}/deny", params)
    if result.get("success"):
        action = "Overridden" if override else "Denied"
        console.print(f"[bold yellow]✗ {action}[/bold yellow] Incident {incident_id}")
    else:
        console.print(f"[bold red]✗ Failed:[/bold red] {result.get('error', 'unknown')}")


@app.command()
def watch():
    """Watch for pending approvals and display incidents in real-time"""
    console.print("[bold]Watching for incidents...[/bold] (Ctrl+C to stop)")
    try:
        while True:
            data = fetch_json("/api/incidents")
            pending = data.get("pending_approvals", [])

            if pending:
                console.clear()
                console.print(Panel.fit("[bold red]⚠  INCIDENT REQUIRES APPROVAL[/bold red]", border_style="red"))

                for inc_id in pending:
                    details = fetch_json(f"/api/incidents/{inc_id}")
                    if "incident_id" in details:
                        table = Table(title=f"Incident: {inc_id}")
                        table.add_column("Field", style="cyan")
                        table.add_column("Value", style="white")

                        alert = details.get("alert", {})
                        table.add_row("Service", alert.get("service", "?"))
                        table.add_row("Alert", alert.get("title", "?"))
                        table.add_row("Severity", f"[bold red]{details.get('severity', '?')}[/bold red]")
                        table.add_row("State", details.get("state", "?"))

                        root_cause = details.get("root_cause", {})
                        if root_cause:
                            table.add_row("Root Cause", root_cause.get("summary", "?"))
                            table.add_row("Confidence", f"{root_cause.get('confidence', 0):.0%}")

                        remediation = details.get("remediation", {})
                        if remediation:
                            table.add_row("Proposed Fix", f"[green]{remediation.get('action', '?')}[/green]")
                            table.add_row("Risk", f"[bold]{remediation.get('risk', '?')}[/bold]")
                            table.add_row("Commands", "\n".join(remediation.get("commands", [])))

                        console.print(table)
                        console.print("\n[bold]Run:[/bold]")
                        console.print(f"  ocli approve {inc_id}")
                        console.print(f"  ocli deny {inc_id}")
                        console.print(f"  ocli deny {inc_id} --override '<your fix>'")
                        console.print()

            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[dim]Watch stopped.[/dim]")


if __name__ == "__main__":
    app()
