# Room — https://munzel.com/room/

A walkable 3D Gaussian-splat version of my bedroom (from the Blender reconstruction), viewable on iPhone, Android and desktop.
Walk with WASD / drag (desktop), the on-screen stick and drag (phone), or **Motion** (phone: walk with the phone; WebXR AR on Android, step detection on iPhone).

Not part of the Jekyll build (`room` is excluded in `_config.yml`); published on its own:

    bash room/deploy.sh            # upload dist/ (the committed live build)
    bash room/deploy.sh --build    # rebuild dist/ from web/ first (Node 20+)

Layout:
- `web/` — viewer (Vite + three.js + Spark). `web/public/assets/`: `room-high.sog` (desktop), `room-mobile.sog` (phones), `exterior.jpg` (window view panorama), `walkmap.json`, `room.json`.
- `dist/` — the build that is live on munzel.com/room.
- `scripts/` — the rendering/training pipeline below (Blender 4.5 Cycles renders, gsplat training on GPU, SOG packaging with `tools/` = @playcanvas/splat-transform).
- `llama_v6r_vs_ref.jpg`, `walls_before_after.jpg` — comparisons from the last rework.

Intermediate data (renders, trained .ply models, the 638 MB source .blend) are not in git; they live on the server under `~/room-stage/` (`out/`, `in/`, `src/`).

## Pipeline

A browser viewer for the bedroom reconstruction (`bedroom_reconstruction.blend`, Blender 4.5) that you can walk around in continuously.

## How it is made

1. **Walk map** (`scripts/bl_occupancy.py`, `scripts/walkmap.py`). The script projects all furniture between 6 cm and 1.95 m height onto the floor at 2 cm resolution, then keeps the cells at least 20 cm from walls and furniture. Output: `web/public/assets/walkmap.json`, run-length encoded.
2. **Training views** (`scripts/gen_views.py`, `scripts/bl_render_views.py`). Camera positions come from farthest-point sampling over the walkable floor, at eye heights 0.9–2.0 m, with 6 directions per position. Cycles renders each view at 1440×1080, 128 spp with OIDN denoising, plus a planar depth pass and an object-index pass that marks the window glass. Colour: AgX "Medium High Contrast", exposure 4.5, white balance 8500 K / tint 10.
   v2 (`scripts/gen_detail_views.py`) adds 455 close-up views at 0.25–1.2 m from the detailed objects: llama, lily, books, sill, bedside items, salt lamp, chair, lamps and bed. It merges them with the first 540 walk-area views into `views_v2.json`.
3. **Exterior** (`scripts/bl_render_pano.py`). A partial equirectangular panorama of everything outside the window (exterior objects only, no glass), taken from P0 = (-0.5, 0.3, 1.6). The viewer maps it onto a 50 m sphere and draws it only through a stencil portal at the glass. The original render only covered the two photo cards (tower facade, bay) in a navy backdrop, so close to the glass the edges showed. `scripts/pano_ext/` (synth.py, common.py) extends it to lat ±89.8°, lon ±100°: the tower is continued by repeating its own floors (lit windows shuffled), the bay by its sky gradient into night sky, and the ground below by projecting the bottom of the bay photo onto a ground plane; the original card pixels are pasted back unchanged. Limits: from extreme positions the synthesised sides repeat and the ground close below is a blurred collage.
4. **Gaussian splats** (`scripts/train_gs.py`, gsplat 1.5.3 with the MCMC strategy). Uses the known cameras and initialises from back-projected depth. Behind glass pixels the panorama is composited; everywhere else the background is black. Gaussian centres are clamped to the room box. Current recipe (v5, cleanest walls): `--iters 36000 --refine_stop 0.6 --noise_stop 0.6 --reg_stop 0.6 --lr_anneal 0.6 --lr_final 0.1 --sh_reg 0.1 --scene_scale 1.0 --depth_mode log --depth_w 0.1 --alpha_w 0.05`, 1.0M splats, on the 995 v3 views plus 240 level-to-up views (`scripts/gen_views_up.py`, ceiling and upper walls). On held-out views this gave about +1 dB PSNR and ~20% less mid-frequency "blotch" on flat areas (`flat_blotch` in the eval log) than the v3 recipe. The 1.5M model scored lower than the 1.0M one, so both tiers use the 1.0M room model (high tier: with the 250k llama model and extended precision; mobile: 120k llama).
   **Llama and magnet** (`scripts/bl_rebuild_llama.py`). The alpaca plush is rebuilt procedurally from the reference photos (voxel-remeshed body, ~417k fleece curves with beige head/neck, felt muzzle with stitching, halter, pompom, felt eyes and ears). The panda fridge magnet is rebuilt as a wooden frame with the rectified photo (`scripts/magnet_rectified.png`). `scripts/select_views.py` picks the training views that see either object, so only those are re-rendered (`scripts/job_v3.sh`).
   **Llama v6** (`scripts/bl_llama_v6.py`, previewed with `scripts/bl_llama_studio.py` / `scripts/job_studio.sh` in neutral light against the photos in `in/llama_ref/`): rounded needle-felt snout (with felt fuzz) carrying the stitching (top ridge, down the front, mouth line), halter at its base and the eyes right behind it, short fleece round the face; small rounded felt ears. Fleece: ~1.4M fine fibres grouped into tufts (~1500 fibres on the body, ~500 on head/neck). Fibres in a tuft share their crimp (wave frequency, phase and plane), the tufts are dome-shaped (shorter fibres at the edge, so partings open between them), body tufts stay together and taper to soft wisps while head tufts splay out; light frizz and 3% flyaways. Without shared crimp the fleece reads as an even cotton-wool fuzz; with too much clumping (clump > 0.8, no splay) it turns into a mop. Shaded as matte keratin fibres (diffuse + sheen + 15% translucency, lighter tips via Hair Info Intercept) rather than Principled Hair, which glowed like fog. White body, cream head with tan patches (stronger on the back of head and neck, crown and round the eyes), tufts share their colour. Pompom: ~2600 chunky yarn ends (r 1 mm) in red/navy/mustard blocks. `scripts/job_llama6.sh TAG` renders it into the room lit by an HDR panorama of the room captured at the llama (`bl_render_pano_at.py`, `WORLD_HDRI`; direct path tracing of the fur in the dim room was too noisy), trains the llama splat models and merges them (also carving out the previous llama's hull).
   **Llama detail model** (`scripts/job_llama.sh`, `scripts/job_merge.sh`). Fur becomes a smooth blob in the room model, so the llama gets its own splat model: `scripts/bl_llama_views.py` places 150 unobstructed close-up cameras; `bl_render_views.py` with `HOLDOUT_KEEP=Llama` renders only the llama (everything else is a holdout, RGBA); `train_gs.py --rgba 0.3` trains 250k (high) / 120k (mobile) splats; `scripts/merge_llama.py` removes the room model's splats inside the llama's visual hull (and within ~9 mm of the new llama splats, protecting the magnet and the sill), then appends the llama splats.
5. **Packaging** (`scripts/pkg_final.sh`, run on the GPU node). Recentres the PLY on the room (`ply_offset.py`), optionally drops SH bands (`ply_sh.py`), and compresses to SOG with `@playcanvas/splat-transform`.
6. **Viewer** (`web/`). Vite + three.js + `@sparkjsdev/spark`:
   - Desktop: drag to look; WASD/arrows or two-finger scroll to walk; click the floor to glide there; R/F or C to change height.
   - Touch: thumbstick bottom-left to walk; drag anywhere else to look; tap the floor to go there; pinch to zoom; Sit/Stand and Motion buttons.
   - Motion (`src/motion.js`): on Android Chrome with ARCore it starts a WebXR `immersive-ar` session, so the phone's tracked position moves the camera 1:1 (the room is drawn opaque over the camera image; Exit returns to the normal view at the new spot). iPhone Safari has no WebXR, so there turning the phone looks around and a step detector on the accelerometer (DeviceMotion) moves you forward along the view direction, about one step length per detected step.
   - No floor marker rings; click/tap on the floor still glides there.
   - WebXR on headsets.
   - Pixel ratio adapts to the frame rate.
   - Splats are sorted by view depth and drawn to 3 sigma (sqrt(8) on phones), as in training; Spark's radial sort and shorter tails made flat walls look mottled.
7. **Deploy** (`scripts/deploy.sh`). Builds, then `rsync`s to `lukas:/var/www/html/room/`.

Coordinates: training happens in Blender coordinates (Z up). The viewer rotates the splats by -90° about X and adds `splatOffset` from `room.json`.
