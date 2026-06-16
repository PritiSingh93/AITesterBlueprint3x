module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });
  const { jiraId, markdown } = req.body;
  if (!jiraId || !markdown) return res.status(400).json({ error: 'Missing jiraId or markdown' });
  // Serverless environments have no persistent filesystem — use the browser download button instead.
  return res.status(200).json({ saved: false, message: 'Server-side saving is not available on Vercel. Use the "Save To File" download button.' });
};
