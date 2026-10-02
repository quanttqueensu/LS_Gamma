import argparse

from lsgamma import experiments

NAME = "YYYY-MM-DD-short-slug"  # matches configs/experiments/<NAME>.toml


def run(cfg):
    # import desk code from lsgamma; don't copy it
    raise NotImplementedError


def main():
    p = argparse.ArgumentParser(description=NAME)
    p.parse_args()
    cfg = experiments.load_config(NAME)
    run_dir = experiments.start_run(NAME, cfg)
    result = run(cfg)
    experiments.save(run_dir, result, "result")
    print(result)
    print(f"run saved to {run_dir} (trial {len(experiments.trials(NAME))})")


if __name__ == "__main__":
    main()
