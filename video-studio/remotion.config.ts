import {Config} from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
// Adjust concurrency to match your machine.
Config.setConcurrency(2);
