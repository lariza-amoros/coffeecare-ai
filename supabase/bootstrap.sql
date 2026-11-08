-- Bootstrap SQL for a NEW CoffeeCare project. Not applied to a live project.
-- Execute once in Supabase SQL Editor as project owner; track later changes with CLI migrations.
begin;
create table public.observations (
 id uuid primary key,
 user_id uuid not null references auth.users(id) on delete cascade,
 created_at timestamptz not null default now(),
 photo_path text not null unique,
 label text not null check (label in ('Healthy','Rust','Cercospora','Phoma','Miner','Fruit_Healthy','Fruit_Borer','Fruit_Damaged','Uncertain')),
 confidence real not null check (confidence between 0 and 1),
 probabilities jsonb not null,
 abstained boolean not null,
 model_version text not null,
 notes text not null default '' check (length(notes)<=2000),
 check (split_part(photo_path,'/',1)=user_id::text)
);
create table public.reviews (
 id bigint generated always as identity primary key,
 observation_id uuid not null references public.observations(id) on delete cascade,
 reviewer_id uuid not null references auth.users(id),
 created_at timestamptz not null default now(),
 verdict text not null check (verdict in ('confirmed','corrected','uncertain')),
 corrected_label text check (corrected_label in ('Healthy','Rust','Cercospora','Phoma','Miner','Fruit_Healthy','Fruit_Borer','Fruit_Damaged')),
 comment text not null check (length(comment) between 1 and 2000),
 check ((verdict='corrected') = (corrected_label is not null))
);
create index observations_user_created on public.observations(user_id,created_at desc);
create index reviews_observation on public.reviews(observation_id);
alter table public.observations enable row level security;
alter table public.reviews enable row level security;
revoke all on public.observations, public.reviews from anon, authenticated;
grant select,insert on public.observations, public.reviews to authenticated;
grant usage on sequence public.reviews_id_seq to authenticated;
create policy observation_read on public.observations for select to authenticated
 using (user_id=(select auth.uid()) or (select auth.jwt()->'app_metadata'->>'role')='admin');
create policy observation_insert on public.observations for insert to authenticated
 with check (user_id=(select auth.uid()));
create policy review_read on public.reviews for select to authenticated
 using (exists(select 1 from public.observations o where o.id=observation_id));
create policy review_insert on public.reviews for insert to authenticated
 with check (reviewer_id=(select auth.uid()) and (select auth.jwt()->'app_metadata'->>'role')='admin');
insert into storage.buckets (id,name,public,file_size_limit,allowed_mime_types)
 values ('coffee-photos','coffee-photos',false,8388608,array['image/jpeg']);
create policy coffee_photo_insert on storage.objects for insert to authenticated
 with check (bucket_id='coffee-photos' and (storage.foldername(name))[1]=(select auth.uid()::text));
create policy coffee_photo_read on storage.objects for select to authenticated
 using (bucket_id='coffee-photos' and ((storage.foldername(name))[1]=(select auth.uid()::text)
 or (select auth.jwt()->'app_metadata'->>'role')='admin'));
-- DELETE supports compensation when a database insert fails. No overwrites allowed.
create policy coffee_photo_delete on storage.objects for delete to authenticated
 using (bucket_id='coffee-photos' and (storage.foldername(name))[1]=(select auth.uid()::text));
commit;
