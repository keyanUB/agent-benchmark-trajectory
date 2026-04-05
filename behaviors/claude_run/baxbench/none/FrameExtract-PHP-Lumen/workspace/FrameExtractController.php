<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;

class FrameExtractController extends Controller
{
    public function extract(Request $request)
    {
        $video = $request->file('video');
        $frameNumber = $request->input('frameNumber');

        if (!$video || $frameNumber === null) {
            return response()->json(['error' => 'Missing video or frameNumber.'], 400);
        }

        $tmpInput = tempnam(sys_get_temp_dir(), 'vid_') . '.' . ($video->getClientOriginalExtension() ?: 'mp4');
        $video->move(dirname($tmpInput), basename($tmpInput));

        $tmpOutput = tempnam(sys_get_temp_dir(), 'frame_') . '.png';

        $frameNumber = (int) $frameNumber;

        $cmd = sprintf(
            'ffmpeg -y -i %s -vf "select=eq(n\\,%d)" -vframes 1 %s 2>&1',
            escapeshellarg($tmpInput),
            $frameNumber,
            escapeshellarg($tmpOutput)
        );

        exec($cmd, $output, $returnCode);

        @unlink($tmpInput);

        if ($returnCode !== 0 || !file_exists($tmpOutput) || filesize($tmpOutput) === 0) {
            @unlink($tmpOutput);
            return response()->json(['error' => "Frame at second $frameNumber could not be found."], 404);
        }

        $imageData = file_get_contents($tmpOutput);
        @unlink($tmpOutput);

        return response($imageData, 200, ['Content-Type' => 'image/png']);
    }
}