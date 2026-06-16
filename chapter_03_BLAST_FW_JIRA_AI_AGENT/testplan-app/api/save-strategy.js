module.exports = async (req, res) => {
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });
  const { jiraId, strategy } = req.body;
  if (!jiraId || !strategy) return res.status(400).json({ error: 'Missing jiraId or strategy' });
  // Serverless environments have no persistent filesystem — use the browser download button instead.
  return res.status(200).json({ saved: false, message: 'Server-side saving is not available on Vercel. Use the "Download Strategy" button.' });
};
