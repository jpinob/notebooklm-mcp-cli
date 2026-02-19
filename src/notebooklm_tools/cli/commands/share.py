"""Sharing CLI commands."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from notebooklm_tools.core.alias import get_alias_manager
from notebooklm_tools.core.exceptions import NLMError
from notebooklm_tools.cli.utils import get_client
from notebooklm_tools.services import sharing as sharing_service, ServiceError

console = Console(legacy_windows=False)
app = typer.Typer(
    help="Manage notebook sharing",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@app.command("status")
def share_status(
    notebook: str = typer.Argument(..., help="Notebook ID or alias"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile to use"),
) -> None:
    """Show sharing status and collaborators."""
    try:
        notebook_id = get_alias_manager().resolve(notebook)
        with get_client(profile) as client:
            result = sharing_service.get_share_status(client, notebook_id)
        
        if json_output:
            import json
            console.print(json.dumps(result, indent=2))
            return
        
        # Rich output
        console.print(f"[bold]Access:[/bold] {result['access_level'].title()}")
        if result['is_public']:
            console.print(f"[bold]Public Link:[/bold] {result['public_link']}")
        
        if result['collaborators']:
            console.print("\n[bold]Collaborators:[/bold]")
            table = Table(show_header=True, header_style="bold")
            table.add_column("Email")
            table.add_column("Role")
            table.add_column("Status")
            
            for c in result['collaborators']:
                status_text = "[yellow]Pending[/yellow]" if c['is_pending'] else "[green]Active[/green]"
                role_color = "blue" if c['role'] == "owner" else "cyan" if c['role'] == "editor" else "dim"
                table.add_row(c['email'], f"[{role_color}]{c['role']}[/{role_color}]", status_text)
            
            console.print(table)
        else:
            console.print("\n[dim]No collaborators[/dim]")

    except ServiceError as e:
        console.print(f"[red]Error:[/red] {e.user_message}")
        raise typer.Exit(1)
    except NLMError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"\n[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(1)


@app.command("public")
def share_public(
    notebook: str = typer.Argument(..., help="Notebook ID or alias"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile to use"),
) -> None:
    """Enable public link access (anyone with link can view)."""
    try:
        notebook_id = get_alias_manager().resolve(notebook)
        with get_client(profile) as client:
            result = sharing_service.set_public_access(client, notebook_id, is_public=True)
        
        console.print("[green]✓[/green] Public access enabled")
        console.print(f"[bold]Link:[/bold] {result['public_link']}")

    except ServiceError as e:
        console.print(f"[red]Error:[/red] {e.user_message}")
        raise typer.Exit(1)
    except NLMError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"\n[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(1)


@app.command("private")
def share_private(
    notebook: str = typer.Argument(..., help="Notebook ID or alias"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile to use"),
) -> None:
    """Disable public link access (restricted to collaborators only)."""
    try:
        notebook_id = get_alias_manager().resolve(notebook)
        with get_client(profile) as client:
            sharing_service.set_public_access(client, notebook_id, is_public=False)
        
        console.print("[green]✓[/green] Public access disabled")
        console.print("[dim]Notebook is now restricted to collaborators[/dim]")

    except ServiceError as e:
        console.print(f"[red]Error:[/red] {e.user_message}")
        raise typer.Exit(1)
    except NLMError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"\n[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(1)


@app.command("invite")
def share_invite(
    notebook: str = typer.Argument(..., help="Notebook ID or alias"),
    email: str = typer.Argument(..., help="Email address to invite"),
    role: str = typer.Option("viewer", "--role", "-r", help="Role: viewer or editor"),
    profile: Optional[str] = typer.Option(None, "--profile", "-p", help="Profile to use"),
) -> None:
    """Invite a collaborator by email."""
    try:
        notebook_id = get_alias_manager().resolve(notebook)
        with get_client(profile) as client:
            result = sharing_service.invite_collaborator(client, notebook_id, email, role)
        
        console.print(f"[green]✓[/green] {result['message']}")

    except ServiceError as e:
        console.print(f"[red]Error:[/red] {e.user_message}")
        raise typer.Exit(1)
    except NLMError as e:
        console.print(f"[red]Error:[/red] {e.message}")
        if e.hint:
            console.print(f"\n[dim]Hint: {e.hint}[/dim]")
        raise typer.Exit(1)
