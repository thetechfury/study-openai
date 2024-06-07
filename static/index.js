$(document).ready(function () {

    $(document).on('click', '.g-forms-li', function () {
        const url = $(this).data('url')
        var loader = '<div class="link-button-loader mb-4"></div>'
        $.ajax({
            type: 'GET',
            url: url,
            beforeSend: function () {
                $(document).find('#id_responses').html(loader)
            },
            success: function (resp) {
                $(document).find('#id_responses').html(resp)
            },
        })
    })

    $(document).on('keyup', '#query-input', function (e) {
        const input_value = $(this).val()
        const input_box = $(document).find('.chat-input')
        const input = $(this)
        const url = $(this).data('url')
        var loader = '<div class="dots-loader"></div>'
        if (event.key === 'Enter' && event.keyCode === 13 && input_value !== '') {
            $.ajax({
                type: 'POST',
                url: url,
                data: {
                    'query': input_value
                },
                beforeSend: function () {
                    input.hide()
                    input_box.append(loader)
                },
                success: function (resp) {
                    input_box.find('.dots-loader').hide()
                    input.show()
                    input.val('')
                    $(document).find('#bot-resp').html(resp.bot_response)
                }
            })
        }
    })
})