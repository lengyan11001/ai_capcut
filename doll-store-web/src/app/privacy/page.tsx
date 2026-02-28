export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-2xl font-bold text-gray-900">Privacy Policy</h1>
      <div className="mt-6 space-y-6 text-gray-600">
        <p>
          We collect only the information necessary to process your order and ship it to you:
          name, email, shipping address, and phone if provided.
        </p>
        <p>
          We do not sell or share your data with third parties for marketing. Payment is
          handled by secure third-party providers; we do not store your full payment details.
        </p>
        <p>
          We may use your email to send order confirmations and shipping updates. You can
          contact us at any time to request access to or deletion of your data.
        </p>
        <p>
          This policy may be updated periodically. Continued use of the site after changes
          constitutes acceptance of the updated policy.
        </p>
      </div>
    </div>
  );
}
