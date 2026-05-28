# SAEF Pixel Annotation

A local Python web app for annotating selected pixels inside images. Multiple users can label the same target pixels, and exports include vote counts and category probabilities per pixel for downstream segmentation workflows.

## Run

```powershell
.\run.bat
```

Then open http://127.0.0.1:8000.

If you are using your own Python installation:

```powershell
python -m pip install -r requirements.txt
python -m pixel_annotator --host 127.0.0.1 --port 8000
```

For trusted network access by several annotators:

```powershell
.\run.bat --host 0.0.0.0 --port 8000
```

Then share `http://<your-machine-ip>:8000`. The current app uses username-based identity, not production authentication.

## Workflow

1. Choose an existing username or create a new one when the app opens.
2. Switch users from the top bar, or open User Settings to add, rename, or delete users.
3. Create, choose, or rename a dataset.
4. Upload one image, or use Batch to add several images through the upload dialog.
5. Select a target pixel on the canvas.
6. Zoom with `-`, `Fit`, `+`, or the mouse wheel, then drag inside the image frame to pan.
7. Use Edit to move the selected target pixel; moving a pixel clears its existing annotations.
8. Use Reset to clear all target pixels and annotations for the current image.
9. Choose a label for that pixel.
10. Rename, recolor, add, or remove labels from the Labels panel.
11. Change usernames or use another browser session so another annotator can label the same pixels.
12. Export JSON or CSV from the top bar.

The app stores datasets, uploaded images, target pixels, and annotations in `data/annotations.sqlite3`. Uploaded image files live in `data/images`.

## Export Shape

JSON exports contain:

```json
{
  "image": { "id": 1, "name": "example.png", "width": 512, "height": 512 },
  "categories": [{ "id": 1, "name": "background", "color": "#44515f" }],
  "pixels": [
    {
      "pixel_id": 1,
      "x": 108,
      "y": 42,
      "total_votes": 3,
      "votes": { "background": 1, "target": 2 },
      "probabilities": { "background": 0.3333333333, "target": 0.6666666667 },
      "consensus": "target"
    }
  ]
}
```

CSV exports contain one row per pixel/category pair.

## Tests

```powershell
.\run.bat --help
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests
```
