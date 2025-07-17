import 'jquery'; // Defines "jQuery" and "$"

import axiosSession from '../../axios.js';

function formatUser(user) {
  if(user.loading) {
    return user.text;
  }

  const $container = $(
    "<div class='select2-result-user clearfix'>" +
    "<div class='select2-result-user__email'>" + user.email + "</div>" +
    "<div class='select2-result-user__name'>" + user.first_name + " " + user.last_name + "</div>" +
    "</div>"
  );

  return $container;
}

export default (collectionId) => ({
  init() {
    $("#user-selection").select2({
      ajax: {
        url: '{% url "api:user_autocomplete" %}',
        data: function (params) {
          // remap the "term" parameter from select2 to "query" so it's
          // consistent with other autocomplete endpoints.
          return {
            query: params.term
          }
        },
        processResults: function (data) {
          return {
            results: data
          };
        },
        delay: 50,
      },
      placeholder: 'Search for a user by email',
      minimumInputLength: 3,
      templateResult: formatUser,
      templateSelection: function (user) {
        return user.email || user.text;
      }
    });
  },
  modalOpen: false,
  errorMessage: '',
  async shareCollectionWithUsers() {
    if ($('#user-selection').val().length === 0) {
      this.errorMessage = 'Please select at least one user to share the collection with.';
      return;
    }

    if (confirm('Are you sure you want to grant additional access to this collection?')) {
      try {
        const resp = await axiosSession.post(`/api/v2/collections/${collectionId}/share/`, {
          user_ids: $('#user-selection').val().map(function (n) {
            return parseInt(n)
          })
        });
      } catch (error) {
        this.errorMessage = error.response.data[0];
        return;
      }
      window.location.reload();
    }
  },
});
