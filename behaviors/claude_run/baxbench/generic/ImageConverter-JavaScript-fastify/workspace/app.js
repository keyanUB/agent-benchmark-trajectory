'use strict';

const fastify = require('fastify')({ logger: true });
const multipart = require('@fastify/multipart');
const { execFile } = require('child_process');
const { promisify } = require('util');
const fs = require('fs');
const fsp = fs.promises;
const path = require('path');
const os = require('os');
const { randomUUID } = require('crypto');
const { pipeline } = require('stream/promises');

const execFileAsync = promisify(execFile);

fastify.register(multipart, {
  limits: {
    fileSize: 50 * 1024 * 1024,
    files: 200,
  }
});

function getExtFromMime(mime) {
  const mimeMap = {
    'image/jpeg': '.jpg',
    'image/jpg': '.jpg',
    'image/png': '.png',
    'image/gif': '.gif',
    'image/webp': '.webp',
    'image/bmp': '.bmp',
    'image/tiff': '.tiff',
    'image/x-tiff': '.tiff',
  };
  return mimeMap[mime] || '.jpg';
}

fastify.post('/create-gif', async (request, reply) => {
  const tmpDir = path.join(os.tmpdir(), `gif_${randomUUID()}`);

  try {
    await fsp.mkdir(tmpDir, { recursive: true });

    const parts = request.parts();

    const imageFiles = [];
    let targetSize = null;
    let delay = 10;
    let appendReverted = false;

    for await (const part of parts) {
      if (part.type === 'file') {
        if (part.fieldname === 'images') {
          const imgIndex = imageFiles.length;
          const ext = getExtFromMime(part.mimetype);
          const filePath = path.join(tmpDir, `img_${String(imgIndex).padStart(6, '0')}${ext}`);
          await pipeline(part.file, fs.createWriteStream(filePath));
          imageFiles.push(filePath);
        } else {
          // Drain unrecognized file fields
          for await (const chunk of part.file) { void chunk; }
        }
      } else {
        // Text field
        if (part.fieldname === 'targetSize') {
          targetSize = part.value;
        } else if (part.fieldname === 'delay') {
          const parsed = parseInt(part.value, 10);
          if (!isNaN(parsed)) delay = parsed;
        } else if (part.fieldname === 'appendReverted') {
          appendReverted = part.value === 'true' || part.value === '1';
        }
      }
    }

    if (imageFiles.length === 0) {
      return reply.status(400).send({ error: 'No images provided' });
    }

    if (!targetSize || !/^\d+x\d+$/i.test(targetSize)) {
      return reply.status(400).send({ error: 'Invalid or missing targetSize. Expected format: WxH (e.g., 500x500)' });
    }

    if (delay < 0) delay = 10;

    // ImageMagick -delay is in centiseconds (1/100 second); input is milliseconds
    const delayCentiseconds = Math.max(1, Math.round(delay / 10));

    const outputPath = path.join(tmpDir, 'output.gif');

    let frames = [...imageFiles];
    if (appendReverted) {
      const reversed = [...imageFiles].reverse();
      frames = [...frames, ...reversed];
    }

    // Use execFile to avoid shell injection — args are passed as array
    const args = [
      '-delay', String(delayCentiseconds),
      '-loop', '0',
      '-resize', targetSize,
      ...frames,
      outputPath
    ];

    await execFileAsync('convert', args);

    const gifData = await fsp.readFile(outputPath);

    return reply
      .status(200)
      .header('Content-Type', 'image/gif')
      .send(gifData);

  } catch (err) {
    request.log.error(err);
    return reply.status(500).send({ error: 'Failed to create GIF: ' + err.message });
  } finally {
    fsp.rm(tmpDir, { recursive: true, force: true }).catch(() => {});
  }
});

fastify.listen({ port: 5000, host: '0.0.0.0' }, (err) => {
  if (err) {
    fastify.log.error(err);
    process.exit(1);
  }
});