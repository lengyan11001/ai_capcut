export default function ContactPage() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-12">
      <h1 className="text-2xl font-bold text-gray-900">Contact</h1>
      <p className="mt-6 text-gray-600">
        For orders, shipping, or general questions, please email us at:
      </p>
      <p className="mt-2">
        <a
          href="mailto:support@example.com"
          className="font-medium text-gray-900 underline hover:no-underline"
        >
          support@example.com
        </a>
      </p>
      <p className="mt-6 text-sm text-gray-500">
        Replace this address with your real contact email in the code or via environment variable.
      </p>
    </div>
  );
}
