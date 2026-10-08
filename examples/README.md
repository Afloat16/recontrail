# Calibration templates

These JSON files illustrate the accepted structure only. Their numbers are not a calibration for your camera. Replace all dimensions, intrinsics, distortion and stereo extrinsics with values measured for your actual imaging setup. `R,t` transform left-camera coordinates into right-camera coordinates. Mislabelled baseline units directly mislabel reconstructed scale.

For a runnable fixture with its own valid synthetic calibration, run:

```bash
python -m recontrail demo -o ../example-capture --run
```

The generated `ground_truth.json` is for independent tests only. The reconstruction pipeline never reads it.
