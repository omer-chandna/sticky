# Examples

`generate_samples.py` draws original photographs (a rectangle, a circle, a star, a small collection, and one angled sticker) and runs the real Sticky pipeline on the angled sticker.

```bash
services/api/.venv/bin/python examples/generate_samples.py
```

Outputs:

- `examples/samples/*.png` — source photographs for tests and demos
- `apps/web/public/samples/` — files the “Try an example” buttons upload
- `apps/web/public/demo/before.png` and `after.png` — the landing comparison

Nothing in these images is a commercial sticker or a copied logo.
