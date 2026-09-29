from supabase import Client, create_client

from app.config import SUPABASE_BUCKET, SUPABASE_SECRET_KEY, SUPABASE_URL


supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def upload_file(local_file_path: str, object_key: str) -> str:
	try:
		with open(local_file_path, "rb") as local_file:
			supabase_client.storage.from_(SUPABASE_BUCKET).upload(object_key, local_file)
	except Exception as exc:
		raise RuntimeError(
			f"Supabase Storage upload failed for bucket {SUPABASE_BUCKET!r}, object {object_key!r}"
		) from exc
	return object_key


def download_file(object_key: str, local_file_path: str) -> str:
	try:
		file_bytes = supabase_client.storage.from_(SUPABASE_BUCKET).download(object_key)
		with open(local_file_path, "wb") as local_file:
			local_file.write(file_bytes)
	except Exception as exc:
		raise RuntimeError(
			f"Supabase Storage download failed for bucket {SUPABASE_BUCKET!r}, object {object_key!r}"
		) from exc
	return local_file_path


def delete_file(object_key: str) -> None:
	try:
		supabase_client.storage.from_(SUPABASE_BUCKET).remove([object_key])
	except Exception as exc:
		raise RuntimeError(
			f"Supabase Storage delete failed for bucket {SUPABASE_BUCKET!r}, object {object_key!r}"
		) from exc