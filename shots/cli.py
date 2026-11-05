"""shots: the commands the Claude Code skills call. Each prints one JSON line so the agent can read the result.

    shots doctor                         check Python packages, Blender and API keys
    shots product-check <product>        render the model from 3 angles beside its photos (check/sheet.jpg)
    shots ad <ad.json> [--provider X]    layout -> repaint -> composite -> verify -> overlay, into <ad folder>/out/
    shots layout | repaint | composite | verify <ad.json>    one step at a time
    shots texture rectify <photo> --corners x,y,x,y,x,y,x,y --size WxH --out face.png
    shots texture unwrap <photo> --box l,t,r,b --wrap 150 --out side.png
    shots relight <ad.json>              re-render the product under light read from the repainted room, into out/relit/
    shots bench briefs|run|relight|judge|accuracy|report <product>    the three-way benchmark, see shots/bench.py
"""
import argparse
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path

from . import blender, composite, config, prompt, repaint, sheets, textures


def emit(data: dict) -> None:
    print(json.dumps(data, default=str))


def out_dir(ad_path: Path) -> Path:
    return ad_path.resolve().parent / "out"


def cmd_doctor(_args) -> int:
    report = {"python": sys.version.split()[0], "packages": {}, "keys": {}}
    for mod in ("numpy", "PIL", "openai", "google.genai", "playwright"):
        try:
            report["packages"][mod] = importlib.util.find_spec(mod) is not None
        except ModuleNotFoundError:
            report["packages"][mod] = False
    path = config.find_blender()
    version = config.blender_version(path) if path else None
    report["blender"] = {"path": str(path) if path else None, "version": ".".join(map(str, version)) if version else None,
                         "ok": bool(version and version[:2] >= config.MIN_BLENDER)}
    for key in ("OPENAI_API_KEY", "GEMINI_API_KEY"):
        report["keys"][key] = bool(config.setting(key))
    report["ready"] = report["blender"]["ok"] and any(report["keys"].values()) and report["packages"]["numpy"]
    emit(report)
    return 0 if report["ready"] else 1


def cmd_product_check(args) -> int:
    folder = config.find_product(args.product)
    check = folder / "check"
    info = blender.views(str(folder), check)
    sheet = sheets.check_sheet(folder, info.get("views", []), check / "sheet.jpg")
    emit({"product": folder.name, "sheet": sheet, "views": [v["file"] for v in info.get("views", [])]})
    return 0


def _scene_prompt(ad_path: Path) -> str:
    spec = blender.resolve_ad(ad_path)
    names = [i["product"].get("display_name", i["product"]["name"]) for i in spec["products"]]
    return prompt.build(spec["scene_prompt"], names)


def cmd_layout(args) -> int:
    emit({"step": "layout", **blender.layout(Path(args.ad), out_dir(Path(args.ad)))})
    return 0


def cmd_repaint(args) -> int:
    ad = Path(args.ad)
    emit({"step": "repaint", **repaint.repaint(out_dir(ad), _scene_prompt(ad), args.provider)})
    return 0


def cmd_composite(args) -> int:
    emit({"step": "composite", **composite.composite(out_dir(Path(args.ad)))})
    return 0


def cmd_verify(args) -> int:
    run = out_dir(Path(args.ad))
    emit({"step": "verify", **composite.verify(Path(args.image) if args.image else run / "plate.png", run)})
    return 0


def cmd_ad(args) -> int:
    ad = Path(args.ad).resolve()
    spec = json.loads(ad.read_text())
    run = out_dir(ad)
    t0 = time.time()
    summary = {"ad": str(ad), "out": str(run)}
    if not args.skip_layout:
        summary["layout"] = blender.layout(ad, run)
    summary["repaint"] = repaint.repaint(run, _scene_prompt(ad), args.provider)
    summary["composite"] = composite.composite(run)
    final = run / "final.png"
    if spec.get("overlay"):
        from . import overlay
        overlay.apply(run / "plate.png", ad.parent / spec["overlay"], final)
    else:
        shutil.copy(run / "plate.png", final)
    summary.update(final=str(final), cost_usd=summary["repaint"]["cost_usd"], seconds=round(time.time() - t0, 1),
                   product_pixels_from_model=0)
    (run / "run.json").write_text(json.dumps(summary, indent=1, default=str))
    emit({k: summary[k] for k in ("final", "cost_usd", "seconds", "product_pixels_from_model")})
    return 0


def cmd_texture(args) -> int:
    if args.kind == "rectify":
        pts = [float(v) for v in args.corners.split(",")]
        w, h = (int(v) for v in args.size.lower().split("x"))
        path = textures.rectify(Path(args.photo), list(zip(pts[::2], pts[1::2])), Path(args.out), (w, h))
    else:
        box = tuple(int(v) for v in args.box.split(","))
        path = textures.unwrap(Path(args.photo), box, Path(args.out), args.wrap)
    emit({"texture": str(path)})
    return 0


def cmd_relight(args) -> int:
    from . import relight
    result = relight.relight(Path(args.ad))
    emit({"plate": str(Path(args.ad).resolve().parent / "out" / "relit" / "plate.png"), "light": result["light"], "verify": result["verify"]})
    return 0


def cmd_bench(args) -> int:
    from . import bench
    if args.step == "briefs":
        emit({"briefs": bench.make_briefs(args.product, args.n)})
    elif args.step == "run":
        emit(bench.run(args.product, args.workers, args.limit))
    elif args.step == "relight":
        emit(bench.relight_all(args.product, args.workers, args.limit))
    elif args.step == "judge":
        emit(bench.judge(args.product, args.workers, arms=args.arms, tag=args.tag))
    elif args.step == "accuracy":
        emit(bench.accuracy(args.product, args.workers))
    else:
        emit(bench.report(args.product, Path(args.out or f"results/{args.product}"), arms=args.arms, tag=args.tag))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="shots", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("doctor").set_defaults(fn=cmd_doctor)
    pc = sub.add_parser("product-check")
    pc.add_argument("product")
    pc.set_defaults(fn=cmd_product_check)
    for name, fn in (("layout", cmd_layout), ("repaint", cmd_repaint), ("composite", cmd_composite), ("ad", cmd_ad), ("verify", cmd_verify)):
        sp = sub.add_parser(name)
        sp.add_argument("ad")
        if name in ("repaint", "ad"):
            sp.add_argument("--provider", choices=["openai", "gemini"])
        if name == "ad":
            sp.add_argument("--skip-layout", action="store_true", help="reuse out/guide.png, layer.png, mask.png")
        if name == "verify":
            sp.add_argument("image", nargs="?")
        sp.set_defaults(fn=fn)
    rl = sub.add_parser("relight")
    rl.add_argument("ad")
    rl.set_defaults(fn=cmd_relight)
    tx = sub.add_parser("texture")
    tx.add_argument("kind", choices=["rectify", "unwrap"])
    tx.add_argument("photo")
    tx.add_argument("--out", required=True)
    tx.add_argument("--corners", help="rectify: top-left, top-right, bottom-right, bottom-left as x,y,...")
    tx.add_argument("--size", default="1000x1000", help="rectify: output WxH, in the face's real proportions")
    tx.add_argument("--box", help="unwrap: body left,top,right,bottom")
    tx.add_argument("--wrap", type=float, default=150)
    tx.set_defaults(fn=cmd_texture)
    bn = sub.add_parser("bench")
    bn.add_argument("step", choices=["briefs", "run", "relight", "judge", "accuracy", "report"])
    bn.add_argument("product")
    bn.add_argument("--n", type=int, default=100)
    bn.add_argument("--workers", type=int, default=4)
    bn.add_argument("--limit", type=int, help="run: only the first N briefs")
    bn.add_argument("--out", help="report: output folder (default results/<product>)")
    bn.add_argument("--arms", type=lambda v: v.split(","), help="judge/report: three arms to compare, e.g. full_model,layout_first,relit")
    bn.add_argument("--tag", help="judge/report: name for this comparison, so its judgements sit beside the main ones")
    bn.set_defaults(fn=cmd_bench)
    args = p.parse_args(argv)
    try:
        return args.fn(args)
    except composite.ProductPixelsChanged as e:
        emit({"error": "product_pixels_changed", "detail": str(e)})
        return 2
    except (FileNotFoundError, KeyError) as e:
        emit({"error": type(e).__name__, "detail": str(e)})
        return 1


if __name__ == "__main__":
    sys.exit(main())
