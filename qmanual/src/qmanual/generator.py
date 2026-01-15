from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .spec import ManualSpec


def _jinja_env(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(enabled_extensions=()),
        keep_trailing_newline=True,
    )


def generate_manual(*, spec: ManualSpec, out_dir: Path, overwrite: bool = False) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    template_dir = Path(__file__).parent / "templates"
    env = _jinja_env(template_dir)

    yml_t = env.get_template("quarto_yml_website.j2")
    (out_dir / "_quarto.yml").write_text(yml_t.render(spec=spec), encoding="utf-8")

    idx_t = env.get_template("index_qmd.j2")
    idx_path = out_dir / "index.qmd"
    if overwrite or not idx_path.exists():
        idx_path.write_text(idx_t.render(spec=spec), encoding="utf-8")

    page_t = env.get_template("page_qmd.j2")
    for sec in spec.pages:
        for item in sec.items:
            p = out_dir / item.path
            p.parent.mkdir(parents=True, exist_ok=True)
            if (not overwrite) and p.exists():
                continue
            p.write_text(
                page_t.render(title=item.title, section=sec.section, path=item.path),
                encoding="utf-8",
            )
