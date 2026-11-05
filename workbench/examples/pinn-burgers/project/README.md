# PINN / Burgers workbench example

Author source: https://github.com/maziarraissi/PINNs
Paper read: https://arxiv.org/abs/1711.10561 (Part I preprint)

`python src/plot_reference.py` regenerates `results/burgers-reference.png` from the authors' `data/burgers_shock.mat`. The input stays unchanged. Install the small plotting dependencies with `pip install -r requirements.txt` if needed.

This example visualizes supplied reference data. It does not present a trained PINN. `src/Burgers.py` is the original TensorFlow 1-era training script and requires its upstream environment. See `docs/UPSTREAM.md` and `LICENSE`.
