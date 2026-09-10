from pathlib import Path
import re


def replace_exact(path: str, old: str, new: str) -> None:
    p = Path(path)
    text = p.read_text()
    if old not in text:
        raise SystemExit(f"expected text not found in {path}:\n{old}")
    p.write_text(text.replace(old, new, 1))


def replace_regex(path: str, pattern: str, replacement: str) -> None:
    p = Path(path)
    text = p.read_text()
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
    if count != 1:
        raise SystemExit(f"expected one regex match in {path}, got {count}: {pattern}")
    p.write_text(updated)


# Auth reminder titles: keep them on the limbo session channel.
auth = "plugins/infrarust-plugin-auth/src/handler.rs"
replace_exact(
    auth,
    "use infrarust_api::limbo::handler::{HandlerResult, LimboHandler, SessionEndReason};\nuse infrarust_api::limbo::session::LimboSession;",
    "use infrarust_api::limbo::handle::SessionHandle;\nuse infrarust_api::limbo::handler::{HandlerResult, LimboHandler, SessionEndReason};\nuse infrarust_api::limbo::session::LimboSession;",
)
replace_exact(auth, "use tokio_util::sync::CancellationToken;\n", "")
replace_regex(
    auth,
    r"    fn spawn_reminder_task\(.*?\n    }\n\n    fn validate_password",
    '''    fn spawn_reminder_task(&self, session: SessionHandle) {
        let interval_secs = self.config.security.title_reminder_interval_seconds;
        if interval_secs == 0 {
            return;
        }

        let config = Arc::clone(&self.config);
        let cancel = session.cancellation_token();

        tokio::spawn(async move {
            let mut interval = tokio::time::interval(Duration::from_secs(interval_secs));
            interval.tick().await;
            loop {
                tokio::select! {
                    _ = interval.tick() => {
                        let title = TitleData::new(
                            parse_colored(&config.messages.reminder_title),
                            parse_colored(&config.messages.reminder_subtitle),
                        )
                        .fade_in(5)
                        .stay(60)
                        .fade_out(10);
                        let _ = session.send_title(title);
                    }
                    () = cancel.cancelled() => { break; }
                }
            }
        });
    }

    fn validate_password''',
)
replace_exact(
    auth,
    "        self.spawn_reminder_task(player_id, session.cancellation_token());",
    "        self.spawn_reminder_task(session.handle());",
)


# Modern limbo: load a surrounding 3x3 chunk batch before position sync.
spawn = "crates/infrarust-core/src/limbo/spawn.rs"
replace_exact(
    spawn,
    '''    send_join_game(client, version, registry).await?;
    send_spawn_position(client, version, registry).await?;
    send_player_position(client, version, registry).await?;
    send_modern_chunk_setup(client, version, registry).await
''',
    '''    send_join_game(client, version, registry).await?;
    send_spawn_position(client, version, registry).await?;
    send_modern_chunk_setup(client, version, registry).await?;
    send_player_position(client, version, registry).await
''',
)
replace_regex(
    spawn,
    r"async fn send_chunk\(.*?\n}\n\nasync fn send_limbo_respawn",
    '''async fn send_chunk(
    client: &mut ClientBridge,
    version: ProtocolVersion,
    registry: &PacketRegistry,
) -> Result<(), CoreError> {
    send_chunk_at(client, 0, 0, version, registry).await
}

async fn send_chunk_at(
    client: &mut ClientBridge,
    chunk_x: i32,
    chunk_z: i32,
    version: ProtocolVersion,
    registry: &PacketRegistry,
) -> Result<(), CoreError> {
    let chunk = CChunkData {
        chunk_x,
        chunk_z,
        num_sections: LIMBO_NUM_SECTIONS,
    };
    let frame = encode_packet(&chunk, version, registry)?;
    client.write_frame(&frame).await
}

async fn send_limbo_respawn''',
)
replace_exact(
    spawn,
    '''    send_chunk(client, version, registry).await?;

    let batch_done = CChunkBatchFinished { batch_size: 1 };
''',
    '''    for chunk_x in -1..=1 {
        for chunk_z in -1..=1 {
            send_chunk_at(client, chunk_x, chunk_z, version, registry).await?;
        }
    }

    let batch_done = CChunkBatchFinished { batch_size: 9 };
''',
)


# Registry extractor: add 26.1/26.2 and use Java 25 for the new version family.
extractor = "tools/registry-extractor/extract-all.sh"
replace_exact(
    extractor,
    '''  "1.21.9:773"
  "1.21.11:774"
)''',
    '''  "1.21.9:773"
  "1.21.11:774"
  "26.1:775"
  "26.2:776"
)''',
)
replace_exact(
    extractor,
    '''start_server() {
  local mc_version="$1"

  cleanup_container
''',
    '''start_server() {
  local mc_version="$1"
  local docker_image="$DOCKER_IMAGE"
  if [[ "$mc_version" == 26.* ]]; then
    docker_image="itzg/minecraft-server:java25"
  fi

  cleanup_container
''',
)
replace_exact(extractor, '    "$DOCKER_IMAGE" >/dev/null', '    "$docker_image" >/dev/null')
