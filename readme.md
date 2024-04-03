# TNC helper for running gridded models through HSPF IWater & PWater subroutines

## Getting started

create conda env with numpy built with mkl

```
$conda create -n tnc python=3.11 numpy pandas
$conda activate tnc
$pip install tnc_runoff@<insert some https url between angle brackets>
```

## Demo

select all gridcells for a model:

```
(tnc)$ tnc find -m HIS
found 9 files...
WRF-NARR_HIS/R17C41/input.json
WRF-NARR_HIS/R17C42/input.json
WRF-NARR_HIS/R17C43/input.json
WRF-NARR_HIS/R18C41/input.json
WRF-NARR_HIS/R18C42/input.json
WRF-NARR_HIS/R18C43/input.json
WRF-NARR_HIS/R19C41/input.json
WRF-NARR_HIS/R19C42/input.json
WRF-NARR_HIS/R19C43/input.json
```

select certain gridcells for a model:

```
(tnc)$ tnc find -m HIS -g R17C42 -g R18C42
found 2 files...
WRF-NARR_HIS/R17C42/input.json
WRF-NARR_HIS/R18C42/input.json
```

select matching gridcells for any model:

```
(tnc)$ tnc find -g R17 -g C42
found 5 files...
WRF-NARR_HIS/R17C41/input.json
WRF-NARR_HIS/R17C42/input.json
WRF-NARR_HIS/R17C43/input.json
WRF-NARR_HIS/R18C42/input.json
WRF-NARR_HIS/R19C42/input.json
```

fetch inputs, run each HRU, upload to cloud storage:

```
(tnc) $ tnc run -m HIS
starting 9 parallel workers to do 9 jobs...
100%|██████████████████████████████████████████████████████████| 9/9 [00:18<00:00,  2.10s/it]
```
