---
layout: page
title: Lorien
permalink: /lorien/
description: An app to prevent you from doomscrolling
nav: false
---

Lorien is a small side-project I built to prevent doomscrolling. The concept is super simple: Before opening Instagram or X, you have to enter the phrase *"I am unblocking for a specific reason that I will now speak out loud. This is a better use of my time than reading or journaling"*. Actually speak the reason out loud, at least in your internal monologue!

The idea is that adding a small amount of intentional friction makes you pause and think about whether you really want to open that app right now. It turns a mindless habit into a conscious decision.

### How it works

- **Block list**: Choose which apps, categories, or websites to block via Apple's built-in picker
- **Unlocking**: Type the configured phrase and choose how many minutes you want to unblock for (default 3 minutes)
- **Re-lock**: The app automatically re-locks when your chosen time is up
- **Live Activity**: While unlocked, a Live Activity on your Lock Screen and Dynamic Island shows the remaining time with a stop button to re-lock early

Under the hood, Lorien uses Apple's Screen Time APIs (`FamilyControls`, `ManagedSettings`, `DeviceActivity`) to block selected apps by default and only unblock them temporarily after entering the phrase. No data is collected.

### Get it

Lorien is free on the [App Store](https://apps.apple.com/app/lorien/id6757672327). The source code is on [GitHub](https://github.com/wdjpng/lorien).
