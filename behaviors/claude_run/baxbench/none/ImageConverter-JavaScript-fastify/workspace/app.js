'use strict';

const fastify = require('fastify')({ logger: true });
const multipart = require('@fastify/multipart');
const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');
const { promisify } = require('util');

fastify.register(multipart, { limits: { fileSize: 50 * 1024 * 1024, files: 100 } });

const execFileAsync = promisify(execFile);

fastify.post('/create-gif', async (request, reply) => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'gifmaker-'));
  const images = [];
  let targetSize = null;
  let delay = 10;
  let appendReverted = false;

  try {
    const parts = request.parts();

    for await (const part of parts) {
      if (part.type === 'file' && part.fieldname === 'images') {
        const ext = path.extname(part.filename || '.bin') || '.bin';
        const filename = path.join(tempDir, `frame_${images.length}${ext}`);
        await new Promise((resolve, reject) => {
          const ws = fs.createWriteStream(filename);
          part.file.pipe(ws);
          ws.on('finish', resolve);
          ws.on('error', reject);
          part.file.on('error', reject);
        });
        images.push(filename);
      } else if (part.type === 'field') {
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

    if (images.length === 0) {
      return reply.status(400).send({ error: 'No images provided' });
    }

    if (!targetSize) {
      return reply.status(400).send({ error: 'targetSize is required' });
    }

    if (!/^\d+x\d+$/i.test(targetSize)) {
      return reply.status(400).send({ error: 'Invalid targetSize format. Expected WxH (e.g. 500x500)' });
    }

    // ImageMagick delay is in centiseconds (1/100s), input is ms
    const delayCentiseconds = Math.max(1, Math.round(delay / 10));

    const frameFiles = appendReverted
      ? [...images, ...[...images].reverse()]
      : images;

    const outputFile = path.join(tempDir, 'output.gif');

    const args = [
      '-delay', String(delayCentiseconds),
      '-loop', '0',
      '-resize', targetSize,
      ...frameFiles,
      outputFile
    ];

    await execFileAsync('convert', args);

    const gifData = fs.readFileSync(outputFile);

    reply.header('Content-Type', 'image/gif');
    return reply.send(gifData);

  } catch (err) {
    request.log.error(err);
    return reply.status(500).send({ error: err.message || 'Internal server error' });
  } finally {
    try {
      fs.rmSync(tempDir, { recursive: true, force: true });
    } catch (_) {
      // ignore cleanup errors
    }
  }
});

fastify.listen({ port: 5000, host: '0.0.0.0' }, (err) => {
  if (err) {
    fastify.log.error(err);
    process.exit(1);
  }
});