'use strict';

const fastify = require('fastify')({ logger: true });
const multipart = require('@fastify/multipart');
const { execFile } = require('child_process');
const { promisify } = require('util');
const fs = require('fs');
const path = require('path');
const os = require('os');
const crypto = require('crypto');

const execFileAsync = promisify(execFile);

const MAX_IMAGES = 20;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB per file
const MAX_DIMENSION = 10000;
const MAX_DELAY_MS = 60000;
const CONVERT_TIMEOUT_MS = 60000;
const ALLOWED_EXTS = new Set(['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif']);

fastify.register(multipart, {
  limits: {
    fileSize: MAX_FILE_SIZE,
    files: MAX_IMAGES + 1,
    fields: 10,
    parts: MAX_IMAGES + 10,
    fieldSize: 1024
  }
});

function validateTargetSize(size) {
  if (typeof size !== 'string') return null;
  const match = /^(\d{1,5})x(\d{1,5})$/.exec(size.trim());
  if (!match) return null;
  const w = parseInt(match[1], 10);
  const h = parseInt(match[2], 10);
  if (w <= 0 || w > MAX_DIMENSION || h <= 0 || h > MAX_DIMENSION) return null;
  return `${w}x${h}`;
}

function safeTempPath(tmpDir, ext) {
  const safeExt = ALLOWED_EXTS.has(ext) ? ext : '.bin';
  const name = `${crypto.randomBytes(16).toString('hex')}${safeExt}`;
  const filePath = path.join(tmpDir, name);
  // Verify path stays within tmpDir (CWE-22)
  const resolved = path.resolve(filePath);
  const resolvedDir = path.resolve(tmpDir);
  if (!resolved.startsWith(resolvedDir + path.sep)) {
    throw new Error('Path traversal detected');
  }
  return resolved;
}

fastify.post('/create-gif', async (request, reply) => {
  let tmpDir = null;

  try {
    tmpDir = await fs.promises.mkdtemp(path.join(os.tmpdir(), 'gifcreator-'));

    const fields = {};
    const imagePaths = [];

    const parts = request.parts();

    for await (const part of parts) {
      if (part.type === 'file') {
        const fieldname = part.fieldname || '';
        if (fieldname !== 'images' && fieldname !== 'images[]') {
          part.file.resume();
          continue;
        }
        if (imagePaths.length >= MAX_IMAGES) {
          part.file.resume();
          continue;
        }

        const origExt = path.extname(part.filename || '').toLowerCase();
        const filePath = safeTempPath(tmpDir, origExt);

        const buffer = await part.toBuffer();
        if (buffer.length === 0) continue;

        await fs.promises.writeFile(filePath, buffer);
        imagePaths.push(filePath);
      } else {
        const name = part.fieldname;
        if (['targetSize', 'delay', 'appendReverted'].includes(name)) {
          fields[name] = part.value;
        }
      }
    }

    if (imagePaths.length === 0) {
      return reply.code(400).send({ error: 'No images provided' });
    }

    if (!fields.targetSize) {
      return reply.code(400).send({ error: 'targetSize is required' });
    }

    const sizeStr = validateTargetSize(fields.targetSize);
    if (!sizeStr) {
      return reply.code(400).send({ error: 'Invalid targetSize. Expected format: WxH (e.g. 500x500), max dimension 10000' });
    }

    let delayMs = 10;
    if (fields.delay !== undefined) {
      const parsed = parseInt(fields.delay, 10);
      if (isNaN(parsed) || parsed < 0 || parsed > MAX_DELAY_MS) {
        return reply.code(400).send({ error: `Invalid delay. Must be an integer between 0 and ${MAX_DELAY_MS}` });
      }
      delayMs = parsed;
    }

    const appendReverted =
      fields.appendReverted === 'true' ||
      fields.appendReverted === '1' ||
      fields.appendReverted === true;

    // ImageMagick delay is in centiseconds (1/100s); input is ms
    const delayCentiseconds = String(Math.max(1, Math.round(delayMs / 10)));

    let frames = [...imagePaths];
    if (appendReverted) {
      frames = [...frames, ...frames.slice().reverse()];
    }

    const outputPath = safeTempPath(tmpDir, '.gif');

    // Build args as array — never interpolate user input into a shell string (CWE-78)
    const args = [];
    for (const frame of frames) {
      args.push('-delay', delayCentiseconds, '-resize', sizeStr, frame);
    }
    args.push('-loop', '0', outputPath);

    try {
      await execFileAsync('convert', args, {
        timeout: CONVERT_TIMEOUT_MS,
        maxBuffer: 100 * 1024 * 1024
      });
    } catch (err) {
      request.log.error({ err }, 'ImageMagick convert failed');
      return reply.code(500).send({ error: 'Failed to create GIF' });
    }

    let gifData;
    try {
      gifData = await fs.promises.readFile(outputPath);
    } catch (err) {
      request.log.error({ err }, 'Failed to read output GIF');
      return reply.code(500).send({ error: 'Failed to read generated GIF' });
    }

    reply.header('Content-Type', 'image/gif');
    reply.header('Content-Length', gifData.length);
    return reply.send(gifData);

  } catch (err) {
    request.log.error({ err }, 'Unexpected error in /create-gif');
    if (!reply.sent) {
      return reply.code(500).send({ error: 'Internal server error' });
    }
  } finally {
    if (tmpDir) {
      fs.promises.rm(tmpDir, { recursive: true, force: true }).catch((err) => {
        fastify.log.warn({ err }, 'Failed to clean up temp directory');
      });
    }
  }
});

fastify.listen({ port: 5000, host: '0.0.0.0' }, (err) => {
  if (err) {
    fastify.log.error(err);
    process.exit(1);
  }
});